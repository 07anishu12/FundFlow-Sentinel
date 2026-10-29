"""Parse JUnit XML from pytest run into reports/live_validation/test_results.json."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
JUNIT_XML = ROOT / "reports" / "live_validation" / "junit.xml"
JSON_OUT = ROOT / "reports" / "live_validation" / "test_results.json"


def convert():
    if not JUNIT_XML.exists():
        print(f"File not found: {JUNIT_XML}")
        return

    tree = ET.parse(JUNIT_XML)
    root = tree.getroot()

    # root is either <testsuites> or <testsuite>
    suite = root if root.tag == "testsuite" else root.find("testsuite")

    total_tests = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    elapsed_time = float(suite.attrib.get("time", 0.0))

    passed = total_tests - failures - errors - skipped

    test_cases = []
    for tc in suite.findall("testcase"):
        tc_name = tc.attrib.get("name")
        tc_file = tc.attrib.get("classname")
        tc_time = float(tc.attrib.get("time", 0.0))

        failure_el = tc.find("failure")
        error_el = tc.find("error")
        skipped_el = tc.find("skipped")

        if failure_el is not None:
            status = "FAILED"
            msg = failure_el.attrib.get("message", failure_el.text)
        elif error_el is not None:
            status = "ERROR"
            msg = error_el.attrib.get("message", error_el.text)
        elif skipped_el is not None:
            status = "SKIPPED"
            msg = skipped_el.attrib.get("message", skipped_el.text)
        else:
            status = "PASSED"
            msg = ""

        test_cases.append({
            "test_name": tc_name,
            "suite_file": tc_file,
            "duration_sec": tc_time,
            "status": status,
            "message": msg,
        })

    report = {
        "summary": {
            "total": total_tests,
            "passed": passed,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "duration_sec": elapsed_time,
            "success_rate_pct": round(passed / total_tests * 100, 2) if total_tests else 0.0,
            "exit_code": 0 if failures == 0 and errors == 0 else 1,
        },
        "tests": test_cases,
    }

    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {JSON_OUT} with {len(test_cases)} test cases (Passed: {passed}/{total_tests})")


if __name__ == "__main__":
    convert()
