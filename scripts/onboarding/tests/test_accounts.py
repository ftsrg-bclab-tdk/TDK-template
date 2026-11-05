import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("accounts", ROOT / "accounts.py")
accounts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(accounts)
CATALOG = json.loads((ROOT / "account-services.json").read_text())
NOW = "2026-11-03T21:00:00Z"
IDS = {"github": "student-name", "overleaf": "student@example.edu",
       "orcid": "0000-0002-1825-0097", "zotero": "student.name", "zenodo": "student-name"}


class AccountsTest(unittest.TestCase):
    def answer(self, state, service, field, value):
        return accounts.apply_answer(CATALOG, state, service, field, value, checked_at=NOW)

    def identified(self):
        state = {}
        for service, value in IDS.items():
            result = self.answer(state, service, "identifier", value)
            self.assertTrue(result["accepted"])
            state = result["accounts"]
        return state

    def test_new_user_has_all_official_links_and_identifier_prompts(self):
        prompts = accounts.prompts(CATALOG)
        self.assertEqual({p["service"] for p in prompts}, set(IDS))
        expected = {"github": "https://github.com/signup", "overleaf": "https://www.overleaf.com/register",
                    "orcid": "https://orcid.org/register", "zotero": "https://www.zotero.org/user/register",
                    "zenodo": "https://zenodo.org/signup/"}
        for p in prompts:
            self.assertEqual(p["field"], "identifier")
            self.assertEqual(p["signup_url"], expected[p["service"]])
            self.assertTrue(p["profile_url"].startswith("https://"))
            self.assertIn("Reuse", p["text"])
            self.assertIn("Never enter a password", p["text"])
            self.assertTrue(CATALOG["services"][p["service"]]["link_verification"]["sources"])

    def test_resume_after_each_answer_preserves_progress(self):
        state = {}
        for index, (service, value) in enumerate(IDS.items(), 1):
            state = self.answer(state, service, "identifier", value)["accounts"]
            # Simulate interruption and the orchestrator's durable JSON reload.
            state = json.loads(json.dumps(state))
            prompts = accounts.prompts(CATALOG, state)
            self.assertEqual(sum(p["field"] == "identifier" for p in prompts), 5-index)
            self.assertEqual(state[service]["identifier"]["value"], value)
            state = self.answer(state, service, "account_attested", True)["accounts"]
        self.assertEqual(accounts.prompts(CATALOG, state), [])
        self.assertTrue(all(x["account"]["status"] == "manual_attested" for x in state.values()))
        self.assertTrue(all(x["access"] == [] for x in state.values()))

    def test_format_never_verifies_account_or_access(self):
        state = self.identified()
        for step in accounts.status(CATALOG, state)["steps"]:
            self.assertEqual(step["format"], "valid")
            self.assertEqual(step["account"], "pending")
            self.assertEqual(step["next_action"], "confirm_account")
            self.assertEqual(step["access"], [])

    def test_invalid_inputs_preserve_previous_answer(self):
        state = self.identified()
        for service, value in [("github", "bad--name"), ("github", "-name"), ("github", "x"*40),
                               ("overleaf", "a..b@example.edu"), ("overleaf", "no-at-sign"),
                               ("orcid", "0000-0002-1825-0098"), ("orcid", "１２３４-0002-1825-0097"),
                               ("zotero", "https://example.org/person"), ("zenodo", "name with space"),
                               ("github", ""), ("github", None), ("github", {"token": "secret"})]:
            with self.subTest(service=service, value=value):
                result = self.answer(state, service, "identifier", value)
                self.assertFalse(result["accepted"])
                self.assertEqual(result["accounts"], state)

    def test_orcid_url_checksum_and_x(self):
        for value in ["https://orcid.org/0000-0002-1825-0097", "0000-0002-1694-233x"]:
            self.assertEqual(accounts.validate_identifier("orcid", value)["status"], "valid")
        self.assertEqual(accounts.validate_identifier("orcid", "https://evil.example/0000-0002-1825-0097")["status"], "invalid")

    def test_reuse_is_idempotent_and_pure(self):
        state = self.identified()
        state = self.answer(state, "github", "account_attested", True)["accounts"]
        before = copy.deepcopy(state)
        result = self.answer(state, "github", "identifier", " Student-Name ")
        self.assertEqual(result["accounts"], before)
        self.assertEqual(state, before)
        result["accounts"]["github"]["identifier"]["value"] = "different"
        self.assertEqual(state, before)

    def test_identifier_change_discards_old_evidence(self):
        state = self.identified()
        state = self.answer(state, "github", "account_attested", True)["accounts"]
        state = accounts.record_check(CATALOG, state, "github", scope="access", outcome="allowed",
                                      method="authenticated_check", checked_at=NOW,
                                      resource="repo:org/project:write")["accounts"]
        result = self.answer(state, "github", "identifier", "other-student")
        self.assertEqual(result["accounts"]["github"]["account"]["status"], "pending")
        self.assertEqual(result["accounts"]["github"]["access"], [])

    def test_network_failure_is_pending_and_not_nonexistence(self):
        state = self.identified()
        for outcome, expected in [("unreachable", "pending"), ("not_found", "failed"), ("found", "verified"), ("stale", "stale")]:
            result = accounts.record_check(CATALOG, state, "github", scope="account", outcome=outcome,
                                           method="public_lookup", checked_at=NOW)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["accounts"]["github"]["account"]["status"], expected)
            self.assertEqual(result["accounts"]["github"]["access"], [])

    def test_access_is_resource_scoped_and_manual_is_labeled(self):
        state = self.identified()
        for resource, method, expected in [("repo:org/one:read", "authenticated_check", "verified"),
                                            ("repo:org/two:write", "manual_access", "manual_attested")]:
            result = accounts.record_check(CATALOG, state, "github", scope="access", outcome="allowed",
                                           method=method, checked_at=NOW, resource=resource)
            self.assertTrue(result["accepted"])
            state = result["accounts"]
            self.assertEqual(state["github"]["access"][-1]["status"], expected)
        self.assertEqual(len(state["github"]["access"]), 2)
        self.assertEqual(state["github"]["account"]["status"], "pending")
        self.assertEqual(accounts.prepare(CATALOG, json.loads(json.dumps(state)))["accounts"], state)
        bad = accounts.record_check(CATALOG, state, "github", scope="access", outcome="allowed",
                                    method="public_lookup", checked_at=NOW, resource="repo:org/one:read")
        self.assertFalse(bad["accepted"])

    def test_secrets_never_echo_or_survive_known_credential_shapes(self):
        state = self.identified()
        for secret in ["ghp_" + "a"*36, "github_pat_" + "a"*60, "Bearer abc", "password=hunter2", "a"*64]:
            result = self.answer(state, "zenodo", "identifier", secret)
            self.assertFalse(result["accepted"])
            self.assertNotIn(secret, json.dumps(result))
        poisoned = copy.deepcopy(state)
        poisoned["github"]["token"] = "private-key-material"
        poisoned["github"]["account"]["evidence"] = {"body": "private-key-material"}
        poisoned["secret-field-private-key-material"] = "private-key-material"
        clean = accounts.prepare(CATALOG, poisoned)
        self.assertNotIn("private-key-material", json.dumps(clean))
        self.assertTrue(clean["diagnostics"])
        rejected = self.answer(state, "github", "password", "private-key-material")
        self.assertFalse(rejected["accepted"])
        self.assertNotIn("private-key-material", json.dumps(rejected))

    def test_display_prompts_do_not_echo_private_email(self):
        state = self.identified()
        self.assertNotIn(IDS["overleaf"], json.dumps(accounts.prompts(CATALOG, state)))

    def test_attestation_requires_boolean_identifier_and_timezone(self):
        for value in ["yes", "true", 1, None]:
            self.assertFalse(self.answer(self.identified(), "github", "account_attested", value)["accepted"])
        self.assertFalse(self.answer({}, "github", "account_attested", True)["accepted"])
        self.assertFalse(accounts.apply_answer(CATALOG, self.identified(), "github", "account_attested", True,
                                               checked_at="2026-11-03")["accepted"])

    def test_corrupt_or_invented_evidence_cannot_claim_verification(self):
        state = self.identified()
        state["github"]["account"] = {"status": "verified", "method": "format",
                                       "checked_at": NOW, "evidence": {"code": "found"}}
        state["overleaf"]["account"] = {"status": "verified", "method": ["public_lookup"],
                                         "checked_at": NOW, "evidence": {"code": "found"}}
        restored = accounts.prepare(CATALOG, state)
        self.assertEqual(restored["accounts"]["github"]["account"]["status"], "pending")
        self.assertEqual(restored["accounts"]["overleaf"]["account"]["status"], "pending")

    def test_declining_attestation_keeps_identifier_and_missing_step(self):
        state = self.identified()
        state = self.answer(state, "github", "account_attested", True)["accounts"]
        state = self.answer(state, "github", "account_attested", False)["accounts"]
        self.assertEqual(state["github"]["identifier"]["value"], IDS["github"])
        self.assertIn("github", {p["service"] for p in accounts.prompts(CATALOG, state)})


if __name__ == "__main__":
    unittest.main()
