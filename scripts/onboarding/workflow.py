"""Accepted human responsibilities and independently observable external steps."""

STEPS = (
    ("repository", "advisor", "Create private organization repository and populate project metadata"),
    ("access", "advisor/student", "Advisor grants project write access; student accepts invitation"),
    ("overleaf", "advisor", "Import whole GitHub repository into premium Overleaf; invite paper collaborators"),
    ("zotero", "advisor/student", "Advisor adds student to Zotero group; student accepts and verifies bibliography refresh"),
    ("workspace", "student", "Clone project and open workspace; install selected optional component tools"),
    ("roundtrip", "advisor/student", "Verify compile and both native sync directions, including modes and symlinks"),
    ("component_checks", "student", "Run required component checks from fresh clone after roundtrip"),
    ("publication", "lead student/advisor", "Prepare meaningful artifact draft; advisor reviews, lead student publishes deliberately"),
)


def observations(config, adapter=None):
    """Adapter may observe, never provision. No adapter means explicit pending.

    No remote implementation is shipped; real disposable pilot remains required.
    Failures are unknown, not nonexistence. Caller must bind evidence to project.
    """
    rows = []
    for key, actor, action in STEPS:
        row = dict(step=key, actor=actor, action=action, status="pending")
        if not config.get("repository"):
            row["reason"] = "repository_unconfigured"
        elif adapter:
            try:
                evidence = adapter.observe(key, config)
                if evidence.get("project") != config.get("repository"):
                    row.update(status="failed", reason="project_identity_mismatch")
                elif evidence.get("status") in {"pending", "failed", "stale", "verified"}:
                    if evidence["status"] == "verified" and not all(evidence.get(k) for k in ("method", "checked_at", "reference")):
                        row.update(status="pending", reason="incomplete_evidence")
                    else:
                        row.update({k: evidence[k] for k in ("status", "method", "checked_at", "reference") if k in evidence})
            except (OSError, TimeoutError):
                row.update(status="pending", reason="observation_unavailable")
        rows.append(row)
    return rows
