"""Pure account onboarding transitions. No filesystem, network, or terminal IO.

The caller loads the catalog, persists returned ``accounts`` after each accepted
answer, and supplies timestamps and any independently obtained check results.
See docs/onboarding-accounts.md for the integration and trust boundaries.
"""

from datetime import datetime
import re


SERVICES = ("github", "overleaf", "orcid", "zotero", "zenodo")
KINDS = dict(zip(SERVICES, ("username", "email", "orcid", "username", "username")))
_SECRET = re.compile(
    r"gh[pousr]_|github_pat_|Bearer\s|-----BEGIN|(?:password|token|secret)\s*[:=]",
    re.IGNORECASE,
)


def _diagnostic(service, field, code):
    # Never interpolate rejected values, arbitrary keys, or remote error bodies.
    return {"service": service if service in SERVICES else None,
            "field": field, "code": code}


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 32:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None
    except ValueError:
        return False


def validate_identifier(service, value):
    """Return normalized identifier or a static error code. No existence claim.

    Zotero/Zenodo checks are conservative input-shape checks, not assertions
    about their full registration policies. Emails use a common ASCII subset.
    """
    if service not in SERVICES:
        return {"status": "invalid", "code": "unknown_service"}
    if not isinstance(value, str) or len(value) > 254:
        return {"status": "invalid", "code": "invalid_identifier"}
    value = value.strip()
    if not value:
        return {"status": "missing", "code": "identifier_required"}
    if _SECRET.search(value):
        return {"status": "invalid", "code": "credential_not_identifier"}
    valid = False
    if service == "github":
        valid = (len(value) <= 39 and "--" not in value
                 and re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", value))
        value = value.lower()
    elif service == "overleaf":
        # Preserve local-part case; normalize only the case-insensitive domain.
        valid = re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                             r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                             r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", value)
        if valid:
            local, domain = value.rsplit("@", 1)
            valid = len(local) <= 64 and not local.startswith(".") and not local.endswith(".") and ".." not in local
            value = local + "@" + domain.lower()
    elif service == "orcid":
        value = value.removeprefix("https://orcid.org/").upper()
        if re.fullmatch(r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]", value):
            digits = value.replace("-", "")
            total = 0
            for digit in digits[:-1]:
                total = (total + int(digit)) * 2
            check = (12 - total % 11) % 11
            valid = digits[-1] == ("X" if check == 10 else str(check))
    else:
        valid = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value)
        # A common accidental paste is a bare hexadecimal API key.
        if re.fullmatch(r"[a-fA-F0-9]{32,}", value):
            return {"status": "invalid", "code": "credential_not_identifier"}
    if not valid:
        return {"status": "invalid", "code": "invalid_identifier"}
    return {"status": "valid", "identifier": {"kind": KINDS[service], "value": value}}


def _pending():
    return {"status": "pending", "method": None, "checked_at": None, "evidence": None}


def _resource(value):
    return (isinstance(value, str) and not _SECRET.search(value)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,127}", value)
            and not re.fullmatch(r"[a-fA-F0-9]{32,}", value))


def _evidence(scope, outcome, method, checked_at, resource=None):
    if not _timestamp(checked_at):
        return None
    if scope == "account":
        if method == "manual_sign_in" and outcome == "attested":
            status = "manual_attested"
        elif method == "public_lookup" and outcome in {"found", "not_found", "unreachable", "stale"}:
            status = {"found": "verified", "not_found": "failed", "unreachable": "pending", "stale": "stale"}[outcome]
        else:
            return None
    elif scope == "access" and _resource(resource):
        if method not in {"authenticated_check", "manual_access"} or outcome not in {"allowed", "denied", "unreachable", "stale"}:
            return None
        status = {"allowed": "verified" if method == "authenticated_check" else "manual_attested",
                  "denied": "failed", "unreachable": "pending", "stale": "stale"}[outcome]
    else:
        return None
    result = {"status": status, "method": method, "checked_at": checked_at,
              "evidence": {"code": outcome}}
    if scope == "access":
        result["resource"] = resource
    return result


def _restore_evidence(raw, scope):
    if raw == _pending() and scope == "account":
        return _pending()
    keys = {"status", "method", "checked_at", "evidence"} | ({"resource"} if scope == "access" else set())
    if not isinstance(raw, dict) or set(raw) != keys:
        return None
    evidence = raw.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != {"code"}:
        return None
    if not all(isinstance(raw.get(k), str) for k in ("status", "method", "checked_at")) or not isinstance(evidence["code"], str):
        return None
    restored = _evidence(scope, evidence["code"], raw["method"], raw["checked_at"], raw.get("resource"))
    return restored if restored == raw else None


def prepare(catalog, existing=None):
    """Validate/sanitize local state; return accounts and static diagnostics.

    Unknown fields are discarded with diagnostics. Existing evidence is a local
    record, not cryptographic proof; only a trusted orchestrator may supply it.
    """
    if catalog.get("schema_version") != 1 or set(catalog.get("services", {})) != set(SERVICES):
        raise ValueError("Unsupported account catalog")
    accounts, diagnostics = {}, []
    if existing is None:
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
        diagnostics.append(_diagnostic(None, "state", "invalid_state"))
    if set(existing) - set(SERVICES):
        diagnostics.append(_diagnostic(None, "state", "unknown_fields_discarded"))
    for service in SERVICES:
        entry = {"identifier": None, "format": {"status": "missing"},
                 "account": _pending(), "access": []}
        raw = existing.get(service, {})
        if not isinstance(raw, dict):
            raw = {}
            diagnostics.append(_diagnostic(service, "state", "invalid_state"))
        if set(raw) - set(entry):
            diagnostics.append(_diagnostic(service, "state", "unknown_fields_discarded"))
        identifier = raw.get("identifier")
        if identifier is not None:
            check = validate_identifier(service, identifier.get("value") if isinstance(identifier, dict) else None)
            if (isinstance(identifier, dict) and set(identifier) == {"kind", "value"}
                    and identifier.get("kind") == KINDS[service] and check["status"] == "valid"):
                entry["identifier"] = check["identifier"]
                entry["format"] = {"status": "valid"}
                restored = _restore_evidence(raw.get("account", _pending()), "account")
                if restored:
                    entry["account"] = restored
                else:
                    diagnostics.append(_diagnostic(service, "account", "invalid_evidence_discarded"))
                access = raw.get("access", [])
                if not isinstance(access, list):
                    access = []
                    diagnostics.append(_diagnostic(service, "access", "invalid_evidence_discarded"))
                for item in access:
                    restored = _restore_evidence(item, "access")
                    if restored and not any(x["resource"] == restored["resource"] for x in entry["access"]):
                        entry["access"].append(restored)
                    else:
                        diagnostics.append(_diagnostic(service, "access", "invalid_evidence_discarded"))
            else:
                diagnostics.append(_diagnostic(service, "identifier", check.get("code", "invalid_identifier")))
        accounts[service] = entry
    return {"accounts": accounts, "diagnostics": diagnostics}


def prompts(catalog, existing=None):
    """Missing-step descriptors only; no raw saved identifiers in display text."""
    state = prepare(catalog, existing)["accounts"]
    result = []
    for service, entry in state.items():
        spec = catalog["services"][service]
        field = "identifier" if entry["identifier"] is None else "account_attested"
        if field == "account_attested" and entry["account"]["method"] == "manual_sign_in" and entry["account"]["status"] == "manual_attested":
            continue
        result.append({"service": service, "field": field,
                       "text": spec["prompt"] if field == "identifier" else
                       "Sign in to your existing account in your browser. Confirm that the saved identifier is yours. Never enter a password or token here.",
                       "kind": KINDS[service] if field == "identifier" else "boolean",
                       "signup_url": spec["signup_url"], "profile_url": spec["profile_url"],
                       "required": True})
    return result


def apply_answer(catalog, existing, service, field, value, *, checked_at=None):
    """Apply one answer. Invalid answers never replace a previously saved value."""
    result = prepare(catalog, existing)
    result["accepted"] = False
    error = None
    if service not in SERVICES:
        error = "unknown_service"
    elif field == "identifier":
        check = validate_identifier(service, value)
        if check["status"] != "valid":
            error = check["code"]
        else:
            entry = result["accounts"][service]
            if entry["identifier"] != check["identifier"]:
                entry.update(identifier=check["identifier"], format={"status": "valid"},
                             account=_pending(), access=[])
            result["accepted"] = True
    elif field == "account_attested":
        if not isinstance(value, bool):
            error = "boolean_required"
        elif result["accounts"][service]["identifier"] is None:
            error = "identifier_required"
        elif not _timestamp(checked_at):
            error = "timestamp_required"
        else:
            entry = result["accounts"][service]
            entry["account"] = _evidence("account", "attested", "manual_sign_in", checked_at) if value else _pending()
            if not value:
                entry["access"] = []
            result["accepted"] = True
    else:
        error = "unknown_field"
    if error:
        result["diagnostics"].append(_diagnostic(service, field if field in {"identifier", "account_attested"} else "answer", error))
    return result


def record_check(catalog, existing, service, *, scope, outcome, method, checked_at, resource=None):
    """Record an injected check result, never execute a check.

    The adapter must bind the result to this exact identifier and resource. It
    must classify timeouts, 401/403, rate limits and ambiguous 404s as unreachable,
    not nonexistent. Pass only enums, never response bodies or credentials.
    """
    result = prepare(catalog, existing)
    result["accepted"] = False
    # Type guards prevent caller data from raising exceptions or entering output.
    evidence = None
    if all(isinstance(x, str) for x in (scope, outcome, method)):
        evidence = _evidence(scope, outcome, method, checked_at, resource)
    if service not in SERVICES or not evidence:
        result["diagnostics"].append(_diagnostic(service, "check", "invalid_check"))
    elif result["accounts"][service]["identifier"] is None:
        result["diagnostics"].append(_diagnostic(service, "identifier", "identifier_required"))
    else:
        entry = result["accounts"][service]
        if scope == "account":
            entry["account"] = evidence
            if outcome in {"not_found", "stale"}:
                entry["access"] = []
        else:
            entry["access"] = [x for x in entry["access"] if x["resource"] != resource] + [evidence]
        result["accepted"] = True
    return result


def status(catalog, existing=None):
    """Summarize account steps, never imply overall onboarding/access completion."""
    result = prepare(catalog, existing)
    result["steps"] = []
    for service, entry in result["accounts"].items():
        action = ("provide_identifier" if entry["identifier"] is None else
                  "confirm_account" if entry["account"]["method"] != "manual_sign_in" or entry["account"]["status"] != "manual_attested" else
                  "account_recorded")
        result["steps"].append({"service": service, "next_action": action,
                                "format": entry["format"]["status"],
                                "account": entry["account"]["status"],
                                "access": entry["access"],
                                "access_requirements": "determined_by_orchestrator"})
    return result
