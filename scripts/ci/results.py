"""Interpret tool results without treating exit zero or a skipped job as proof."""
import math


def interpret(kind, returncode, report=None, *, strict=False):
    if returncode not in (0, 1):
        return {"outcome": "unknown", "gate_outcome": "fail", "reason": "technical execution failure"}
    if kind == "writing":
        if (not isinstance(report, dict) or type(report.get("ok")) is not bool or
                not isinstance(report.get("rules"), list) or not report["rules"] or
                not isinstance(report.get("findings"), list)):
            raise ValueError("Missing or malformed paper lint JSON")
        seen = set()
        for rule in report["rules"]:
            if (not isinstance(rule, dict) or not isinstance(rule.get("rule"), str) or
                    rule["rule"] in seen or not isinstance(rule.get("status"), str)):
                raise ValueError("Invalid or duplicate lint rule")
            seen.add(rule["rule"])
            if rule["status"] == "error":
                return {"outcome": "unknown", "gate_outcome": "fail", "reason": "lint rule execution error"}
        findings = bool(report["findings"]) or returncode == 1 or not report["ok"]
        return {"outcome": "findings" if findings else "pass",
                "gate_outcome": "fail" if strict and (returncode or not report["ok"]) else "pass",
                "reason": "strict submission" if strict else "writing findings are advisory"}
    if kind in ("tests", "proof", "benchmark"):
        if not isinstance(report, dict) or report.get("schema") != "component-result/v1" or report.get("kind") != kind:
            raise ValueError("Expected component-result/v1 for " + kind)
        outcome = report.get("outcome")
        if outcome not in ("pass", "verified", "violated", "unknown"):
            raise ValueError("Invalid adapter outcome")
        if kind == "proof":
            obligations = report.get("obligations")
            if not isinstance(obligations, list) or not obligations:
                raise ValueError("Proof has no declared obligations")
            ids = set()
            for obligation in obligations:
                if (not isinstance(obligation, dict) or not isinstance(obligation.get("id"), str) or
                        not obligation["id"] or obligation["id"] in ids or
                        obligation.get("outcome") not in ("verified", "violated", "unknown")):
                    raise ValueError("Invalid proof obligation")
                ids.add(obligation["id"])
            if not isinstance(report.get("bounds"), dict) or not isinstance(report.get("assumptions"), list):
                raise ValueError("Proof must record bounds and assumptions")
            values = {o["outcome"] for o in obligations}
            expected = "violated" if "violated" in values else "unknown" if "unknown" in values else "verified"
            if expected != outcome:
                raise ValueError("Proof summary disagrees with its obligations")
        elif kind == "tests":
            counts = report.get("tests", {})
            if (not isinstance(counts, dict) or set(counts) != {"passed", "failed", "skipped"} or
                    any(type(n) is not int or n < 0 for n in counts.values()) or
                    counts["passed"] + counts["failed"] == 0):
                raise ValueError("No executed test evidence")
            if outcome == "pass" and counts["failed"]:
                raise ValueError("Passing test report contains failures")
        else:
            measurements = report.get("measurements")
            if (report.get("mode") not in ("smoke", "full") or not isinstance(report.get("parameters"), dict)
                    or not isinstance(measurements, list) or not measurements):
                raise ValueError("Benchmark needs mode, parameters and measurements")
            for measurement in measurements:
                if (not isinstance(measurement, dict) or not isinstance(measurement.get("name"), str)
                        or not isinstance(measurement.get("unit"), str)
                        or type(measurement.get("value")) not in (float, int)
                        or not math.isfinite(measurement["value"])):
                    raise ValueError("Invalid benchmark measurement")
        return {"outcome": outcome, "gate_outcome": "pass" if returncode == 0 and outcome in ("pass", "verified") else "fail",
                "reason": "structured adapter evidence"}
    return {"outcome": "pass" if returncode == 0 else "violated",
            "gate_outcome": "pass" if returncode == 0 else "fail", "reason": "command exit"}
