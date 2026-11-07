#!/usr/bin/env python3
"""Check official-source freshness and retain candidates without accepting replacements."""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.config import read_json, inside

MAX_DOWNLOAD = 16 * 1024 * 1024


def download(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Expected a public HTTPS source URL")
    request = urllib.request.Request(url, headers={"User-Agent":"TDK-reference-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(MAX_DOWNLOAD+1)
            if len(body) > MAX_DOWNLOAD:
                raise ValueError("Source exceeds 16 MiB download bound")
            return {"status":response.status,"url":response.url,"media_type":response.headers.get_content_type(),"body":body}
    except urllib.error.HTTPError as exc:
        return {"status":exc.code,"url":url,"media_type":None,"body":b"","error":"HTTP "+str(exc.code)}
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        return {"status":None,"url":url,"media_type":None,"body":b"","error":str(exc)}


class Links(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.links = base, set()
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.add(urllib.parse.urljoin(self.base,href))


def check_manifest(manifest, output, fetch=download, checked_at=None):
    if manifest.get("schema") != "official-references/v1" or not isinstance(manifest.get("sources"),list):
        raise ValueError("Expected official-references/v1")
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    checked_at = checked_at or datetime.now(timezone.utc).isoformat()
    report = {"schema":"reference-freshness/v1","checked_at":checked_at,"context":manifest["context"],
              "human_reviewed_at":manifest["reviewed_at"],"acceptance":"not_performed","sources":[],"discovery":{}}
    seen = set()
    current_year = datetime.fromisoformat(checked_at).year
    for source in manifest["sources"]:
        identifier = source.get("id")
        if not isinstance(identifier,str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*",identifier) or identifier in seen:
            raise ValueError("Invalid or duplicate source ID")
        seen.add(identifier)
        if type(source.get("required")) is not bool:
            raise ValueError("Source required must be boolean")
        expected = source["retrieval"].get("sha256")
        item = {"id":identifier,"required":source["required"],"retrieval":"unresolved",
                "bytes":"not_checked","applicability":source["applicability"]["status"],
                "human_review_performed":False,"expected_sha256":expected}
        if source["category"] == "faculty" and manifest["context"]["faculty_year"] < current_year:
            item["applicability"] = "stale_cycle"
        if source.get("url"):
            response = fetch(source["url"])
            item.update(http_status=response["status"],final_url=response["url"],media_type=response["media_type"])
            if response["status"] != 200:
                item.update(retrieval="unavailable",problem=response.get("error"))
            elif not response["body"].startswith(b"%PDF-") or response["media_type"] not in ("application/pdf","application/octet-stream"):
                item.update(retrieval="invalid_document",problem="HTTP success is not a valid PDF")
            else:
                actual = hashlib.sha256(response["body"]).hexdigest()
                target = output/"candidates"/(identifier+".pdf")
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(response["body"])
                item.update(retrieval="retrieved",sha256=actual,size=len(response["body"]),
                            bytes="unchanged" if expected == actual else "changed" if expected else "candidate",
                            candidate=str(target.relative_to(output)))
        for url in source["discovery_urls"]:
            if url not in report["discovery"]:
                response = fetch(url)
                links = Links(response["url"])
                if response["status"] == 200 and response["media_type"] == "text/html":
                    links.feed(response["body"].decode("utf-8",errors="replace"))
                report["discovery"][url] = {"http_status":response["status"],"sha256":hashlib.sha256(response["body"]).hexdigest() if response["body"] else None,
                                            "links":sorted(links.links),"review":"human_link_review_required"}
        item["readiness"] = "pass" if item["retrieval"] == "retrieved" and item["bytes"] == "unchanged" and item["applicability"] == "confirmed" else "fail"
        report["sources"].append(item)
    report["readiness"] = "fail" if any(s["required"] and s["readiness"] != "pass" for s in report["sources"]) else "pass"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,default=Path("docs/official-references/sources.json"))
    parser.add_argument("--out",type=Path,default=Path(".project/reference-freshness"))
    args = parser.parse_args()
    try:
        manifest, raw = read_json(args.manifest)
        report = check_manifest(manifest,args.out)
        report["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        (args.out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({"readiness":report["readiness"],"required_findings":[s["id"] for s in report["sources"] if s["required"] and s["readiness"]!="pass"]}))
        return 0 if report["readiness"] == "pass" else 1
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
