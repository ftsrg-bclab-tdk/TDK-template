"""GitHub adapters for disposable onboarding pilots; no import-time requests.

The gh credential store owns authentication. No token enters project/state data.
New invitations require authenticated organization 2FA-policy readback. GitHub
enforces it at acceptance; invitation issuance is not accepted access evidence.
"""
import base64
import copy
from datetime import datetime, timezone
import json
import re
import subprocess

from ci.config import validate_project


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Expected organization/repository identity")
    return value


class Gh:
    def request(self, method, endpoint, body=None):
        command = ["gh", "api", "--hostname", "github.com", "--include", "--method", method, endpoint]
        if body is not None:
            command += ["--input", "-"]
        try:
            result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                                    capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("GitHub request unavailable; no absence or success inferred") from None
        # gh --include emits the HTTP status and headers before the JSON body.
        match = re.search(r"HTTP/[^ ]+ (\d{3})[^\n]*\n", result.stdout)
        if not match:
            raise ValueError("GitHub response status unavailable; check gh authentication")
        code = int(match[1])
        payload = result.stdout[match.end():].replace("\r\n", "\n").split("\n\n", 1)
        text = payload[1].strip() if len(payload) == 2 else ""
        try:
            value = json.loads(text) if text else None
        except json.JSONDecodeError:
            raise ValueError("GitHub returned an unreadable response") from None
        if code not in (200, 201, 204, 404):
            raise ValueError("GitHub request failed (HTTP " + str(code) + "); state not advanced")
        return code, value


def github_account(remote, expected_login=None):
    code, user = remote.request("GET", "user")
    if code != 200 or not isinstance(user, dict) or not user.get("login"):
        raise ValueError("Authenticated GitHub account unavailable")
    if expected_login and user["login"].lower() != expected_login.lower():
        raise ValueError("Authenticated GitHub account differs from saved student identifier")
    return {"login": user["login"], "id": user.get("id"),
            "two_factor": "verified" if user.get("two_factor_authentication") is True else
                          "disabled" if user.get("two_factor_authentication") is False else "unavailable",
            "method": "github_authenticated_user", "checked_at": datetime.now(timezone.utc).isoformat()}


def inspect_repository(remote, repository):
    repository = identity(repository)
    code, data = remote.request("GET", "repos/" + repository)
    if code == 404:
        return {"status": "pending", "reason": "missing_or_inaccessible", "repository": repository}
    if not isinstance(data, dict) or data.get("full_name", "").lower() != repository.lower():
        raise ValueError("Repository identity mismatch")
    return {"status": "observed", "repository": repository, "id": data.get("id"),
            "private": data.get("private") is True, "permissions": data.get("permissions", {}),
            "checked_at": datetime.now(timezone.utc).isoformat(), "method": "github_repository"}


def inspect_access(remote, repository, username):
    repository = identity(repository)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username):
        raise ValueError("Invalid collaborator username")
    code, data = remote.request("GET", "repos/" + repository + "/collaborators/" + username + "/permission")
    if code == 200:
        login = data.get("user", {}).get("login", "")
        if login.lower() != username.lower():
            raise ValueError("Collaborator identity mismatch")
        role = data.get("role_name", data.get("permission"))
        return {"repository": repository, "user": username, "status": "observed",
                "role": role, "matches_student_write": role == "write",
                "outside_collaborator": "not_proven_by_effective_permission",
                "two_factor": "not_proven_by_permission", "method": "github_collaborator_permission"}
    return {"repository": repository, "user": username, "status": "pending",
            "reason": "access_missing_or_inaccessible", "invitation": "not_inferred"}


def invite_pilot(remote, repository, username, *, execute=False):
    repository = identity(repository)
    owner, name = repository.split("/")
    if owner != "FTSRG-BCLab-TDK" or not name.startswith("onboarding-pilot-"):
        raise ValueError("Invitations are pilot-only until disposable acceptance/access checks pass")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username):
        raise ValueError("Invalid collaborator username")
    if not execute:
        return {"status": "planned", "repository": repository, "user": username,
                "permission": "write", "requires": "authenticated org-required-2FA readback"}
    actor = github_account(remote)
    code, membership = remote.request("GET", "orgs/" + owner + "/memberships/" + actor["login"])
    if code != 200 or membership.get("state") != "active" or membership.get("role") != "admin":
        raise ValueError("Pilot invitations require authenticated organization owner")
    code, org = remote.request("GET", "orgs/" + owner)
    if code != 200 or org.get("two_factor_requirement_enabled") is not True:
        raise ValueError("Organization 2FA enforcement is absent or unknown; invitation blocked")
    repo = inspect_repository(remote, repository)
    if repo.get("private") is not True or repo.get("permissions", {}).get("admin") is not True:
        raise ValueError("Private repository and advisor admin access must be observed before inviting")
    code, membership = remote.request("GET", "orgs/" + owner + "/memberships/" + username)
    if code != 404:
        raise ValueError("Invitee is an organization member or membership is unclear; outside-only grant requires review")
    access = inspect_access(remote, repository, username)
    if access["status"] == "observed" and access.get("role") not in (None, "none"):
        if not access.get("matches_student_write"):
            raise ValueError("Existing access differs from student write; refusing to change it")
        return {**access, "status": "accepted", "outside_collaborator": "verified_nonmember",
                "org_2fa_required": True, "actor": actor["login"]}
    # Resume without re-sending an already pending invitation.
    for page in range(1, 101):
        code, invitations = remote.request("GET", "repos/" + repository + "/invitations?per_page=100&page=" + str(page))
        if code != 200 or not isinstance(invitations, list):
            raise ValueError("Pending invitations unavailable; refusing duplicate invitation")
        for invitation in invitations:
            if invitation.get("invitee", {}).get("login", "").lower() == username.lower():
                if invitation.get("permissions") not in ("write", "push"):
                    raise ValueError("Existing invitation has a different permission")
                return {"status": "pending", "repository": repository, "user": username,
                        "invitation_id": invitation["id"], "org_2fa_required": True}
        if len(invitations) < 100:
            break
    else:
        raise ValueError("Invitation pagination limit reached; no mutation performed")
    code, invitation = remote.request("PUT", "repos/" + repository + "/collaborators/" + username, {"permission": "push"})
    if code not in (201, 204):
        raise ValueError("Invitation response is not successful; re-observe before retry")
    return {"status": "pending", "repository": repository, "user": username,
            "invitation_id": invitation.get("id") if isinstance(invitation, dict) else None,
            "org_2fa_required": True, "actor": actor["login"],
            "next_action": "Student accepts after enabling 2FA; rerun to verify accepted write access"}


def provision_pilot(remote, config, template, root, *, execute=False):
    repository, template = identity(config["repository"]), identity(template)
    owner, name = repository.split("/")
    if owner != "FTSRG-BCLab-TDK" or not name.startswith("onboarding-pilot-") or repository == template:
        raise ValueError("Provisioning is pilot-only until a disposable pilot passes; use FTSRG-BCLab-TDK/onboarding-pilot-NAME")
    desired = copy.deepcopy(config)
    desired.update(repository=repository, role="project")
    validate_project(desired, root)
    if not execute:
        return {"status": "planned", "repository": repository, "template": template,
                "role": "project", "actions": ["verify advisor identity, organization-required 2FA and owner role",
                    "create private repository if absent", "initialize shared config as project", "read back and verify"]}
    actor = github_account(remote)
    code, member = remote.request("GET", "orgs/" + owner + "/memberships/" + actor["login"])
    if code != 200 or member.get("state") != "active" or member.get("role") != "admin":
        raise ValueError("Repository creation requires verified active organization owner")
    code, org = remote.request("GET", "orgs/" + owner)
    if code != 200 or org.get("two_factor_requirement_enabled") is not True:
        raise ValueError("Organization-required 2FA must be verified before provisioning")
    code, source = remote.request("GET", "repos/" + template)
    if code != 200 or source.get("is_template") is not True:
        raise ValueError("Source must be an accessible GitHub template")
    code, target = remote.request("GET", "repos/" + repository)
    if code == 404:
        # Only a verified org owner reaches this absence/create path.
        remote.request("POST", "repos/" + template + "/generate",
                       {"owner": owner, "name": name, "private": True, "include_all_branches": False})
        code, target = remote.request("GET", "repos/" + repository)
    if (code != 200 or target.get("full_name", "").lower() != repository.lower()
            or target.get("private") is not True or target.get("archived")
            or target.get("owner", {}).get("login", "").lower() != owner.lower()
            or target.get("template_repository", {}).get("full_name", "").lower() != template.lower()):
        raise ValueError("Existing/generated repository conflicts with private owner/template requirements")
    endpoint = "repos/" + repository + "/contents/project.json"
    code, content = remote.request("GET", endpoint)
    if code != 200 or content.get("encoding") != "base64":
        raise ValueError("Generated project config not ready; rerun without creating another repository")
    try:
        observed = json.loads(base64.b64decode(content["content"]))
    except (ValueError, KeyError):
        raise ValueError("Generated project config is unreadable") from None
    validate_project(observed, root)
    if observed != desired:
        # Only untouched template initialization or exact desired retry is allowed.
        if observed.get("role") != "template" or observed.get("repository") not in (None, template):
            raise ValueError("Remote project config has independent edits; refusing to overwrite")
        for field in ("components", "paper_entrypoints", "paper_main"):
            if observed[field] != desired[field]:
                raise ValueError("Template/component configuration drift; review before provisioning")
        # Metadata changes are not automatically applied remotely; bounded source
        # editing remains a local advisor preview/application after cloning.
        if observed["metadata"] != desired["metadata"]:
            raise ValueError("Remote metadata differs; provision from unchanged template config then edit locally")
        remote.request("PUT", endpoint, {
            "message": "Initialize private student project identity",
            "sha": content["sha"],
            "content": base64.b64encode((json.dumps(desired, indent=2) + "\n").encode()).decode(),
        })
    code, verified = remote.request("GET", endpoint)
    if code != 200 or json.loads(base64.b64decode(verified["content"])) != desired:
        raise ValueError("Project configuration write was not verified; retry by observing current state")
    return {"status": "verified", "repository": repository, "repository_id": target["id"],
            "role": "project", "config_blob": verified["sha"], "actor": actor["login"],
            "checked_at": datetime.now(timezone.utc).isoformat(), "template": template,
            "access": "pending_2fa_and_invitation", "method": "github_api_readback"}
