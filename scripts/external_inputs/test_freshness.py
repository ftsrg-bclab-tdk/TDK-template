import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from freshness import check_manifest


class FreshnessTests(unittest.TestCase):
    def test_outage_html_changed_bytes_and_applicability_are_distinct(self):
        good = b"%PDF-1.7\nreference"
        base = {"id":"reference","required":True,"category":"faculty","url":"https://example.org/ref.pdf","discovery_urls":[],
                "retrieval":{"sha256":hashlib.sha256(good).hexdigest()},"applicability":{"status":"confirmed"}}
        sources=[]
        for identifier in ("good","outage","html","changed","unresolved","review"):
            value=copy.deepcopy(base);value["id"]=identifier;value["url"]="https://example.org/"+identifier
            if identifier=="unresolved":value["url"]=None
            if identifier=="review":value["applicability"]["status"]="needs_review"
            sources.append(value)
        def fetch(url):
            name=url.rsplit('/',1)[1]
            return {"status":403 if name=="outage" else 200,"url":url,"media_type":"text/html" if name=="html" else "application/pdf",
                    "body":b"<html>shell</html>" if name=="html" else good+b"new" if name=="changed" else good}
        manifest={"schema":"official-references/v1","context":{"faculty_year":2026},"reviewed_at":"2026-11-01T00:00:00+00:00","sources":sources}
        with tempfile.TemporaryDirectory() as temp:
            report=check_manifest(manifest,Path(temp)/"fresh",fetch,checked_at="2026-11-04T00:00:00+00:00")
            results={s["id"]:s for s in report["sources"]}
            self.assertEqual(results["good"]["readiness"],"pass")
            self.assertEqual(results["outage"]["retrieval"],"unavailable")
            self.assertEqual(results["html"]["retrieval"],"invalid_document")
            self.assertEqual(results["changed"]["bytes"],"changed")
            self.assertEqual(results["unresolved"]["retrieval"],"unresolved")
            self.assertEqual(results["review"]["applicability"],"needs_review")
            self.assertEqual(report["readiness"],"fail")
            self.assertEqual(report["acceptance"],"not_performed")
            stale=check_manifest(manifest,Path(temp)/"stale",fetch,checked_at="2027-01-01T00:00:00+00:00")
            self.assertEqual(stale["sources"][0]["applicability"],"stale_cycle")
