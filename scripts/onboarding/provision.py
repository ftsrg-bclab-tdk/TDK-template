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
from readme.badges import invalidated


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


def read_content(remote, repository, path, ref=None):
    endpoint = "repos/" + repository + "/contents/" + path
    code, data = remote.request("GET", endpoint + ("?ref=" + ref if ref else ""))
    if code != 200 or data.get("encoding") != "base64":
        raise ValueError("Repository content unavailable: " + path)
    return data, base64.b64decode(data["content"]).decode()


def tree(remote, repository, ref):
    code, data = remote.request("GET", "repos/" + repository + "/git/trees/" + ref + "?recursive=1")
    if code != 200 or data.get("truncated") is not False or not isinstance(data.get("tree"), list):
        raise ValueError("Complete generation tree unavailable")
    return {item["path"]: (item["mode"], item["sha"]) for item in data["tree"] if item["type"] != "tree"}


def provision_pilot(remote, config, template, root, *, execute=False, prior=None, persist=None):
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
    # Persist the immutable source before generation: GitHub generation has no ref
    # parameter, so the generated snapshot must independently match this tree.
    if prior:
        if prior.get("repository") != repository or prior.get("template") != template:
            raise ValueError("Provision receipt identity conflict")
        baseline = prior.get("template_baseline_sha")
        if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
            raise ValueError("Prior receipt has no proven generation baseline")
    else:
        code, commit = remote.request("GET", "repos/" + template + "/commits/" + source.get("default_branch", "main"))
        baseline = commit.get("sha") if code == 200 else None
        if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
            raise ValueError("Template baseline unavailable")
    _, source_text = read_content(remote, template, "project.json", baseline)
    source_config = json.loads(source_text)
    validate_project(source_config, root)
    for field in set(desired) - {"role", "repository", "metadata"}:
        if source_config[field] != desired[field]:
            raise ValueError("Template/component configuration drift; no repository created")
    if source_config["role"] != "template" or any(desired["metadata"].get(k) != v for k, v in source_config["metadata"].items()):
        raise ValueError("Source template metadata must be retained unchanged")
    # New expectations may describe unchanged source; existing template metadata
    # must remain identical. No paper text is changed by provisioning.
    for macro, item in desired["metadata"].items():
        if macro in source_config["metadata"]:
            if item != source_config["metadata"][macro]:
                raise ValueError("Template metadata replacement requires local review")
        else:
            _, paper = read_content(remote, template, desired["paper_main"], baseline)
            from setup import declaration
            start, end = declaration(paper, macro)
            if item != {"expected": paper[start:end], "value": paper[start:end]}:
                raise ValueError("Metadata expectation differs from template source")
    readmes = {}
    for path in ("README.md", "paper/README.md"):
        _, original = read_content(remote, template, path, baseline)
        readmes[path] = (original, invalidated(original))
    expected_tree = tree(remote, template, baseline)
    journal = {"status": "prepared", "repository": repository, "template": template,
               "template_baseline_sha": baseline}
    if persist is None:
        raise ValueError("Provisioning requires durable receipt persistence before creation")
    if not prior:
        persist(journal)
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
    code, head = remote.request("GET", "repos/" + repository + "/commits/" + target.get("default_branch", "main"))
    observed_tree = tree(remote, repository, head["sha"])
    mutable = {"project.json", "README.md", "paper/README.md"}
    if {k: v for k, v in expected_tree.items() if k not in mutable} != {k: v for k, v in observed_tree.items() if k not in mutable}:
        raise ValueError("Generated contents do not match captured template baseline")
    for path in mutable:
        if path not in expected_tree or path not in observed_tree or expected_tree[path][0] != observed_tree[path][0]:
            raise ValueError("Generated mutable-file modes differ from baseline")
    for path in ("README.md", "paper/README.md"):
        original, replacement = readmes[path]
        content, observed_text = read_content(remote, repository, path)
        if observed_text not in (original, replacement):
            raise ValueError("Remote README has independent edits")
    # Preflight all mutable files before any update.
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
        if observed != source_config:
            raise ValueError("Remote project config has independent edits; refusing to overwrite")
        remote.request("PUT", endpoint, {
            "message": "Initialize private student project identity",
            "sha": content["sha"],
            "content": base64.b64encode((json.dumps(desired, indent=2) + "\n").encode()).decode(),
        })
    for path in ("README.md", "paper/README.md"):
        original, replacement = readmes[path]
        content, observed_text = read_content(remote, repository, path)
        if observed_text == original and original != replacement:
            remote.request("PUT", "repos/" + repository + "/contents/" + path, {
                "message": "Invalidate inherited template status", "sha": content["sha"],
                "content": base64.b64encode(replacement.encode()).decode()})
        _, verified_text = read_content(remote, repository, path)
        if verified_text != replacement:
            raise ValueError("README initialization was not verified; retry with saved receipt")
    code, verified = remote.request("GET", endpoint)
    if code != 200 or json.loads(base64.b64decode(verified["content"])) != desired:
        raise ValueError("Project configuration write was not verified; retry by observing current state")
    return {"status": "verified", "repository": repository, "repository_id": target["id"],
            "template_baseline_sha": baseline, "generation_tree_verified": True,
            "role": "project", "config_blob": verified["sha"], "actor": actor["login"],
            "checked_at": datetime.now(timezone.utc).isoformat(), "template": template,
            "access": "pending_2fa_and_invitation", "method": "github_api_readback"}
