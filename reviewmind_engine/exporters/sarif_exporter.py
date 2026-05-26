import json
from reviewmind_engine.finding import Finding
from reviewmind_engine.engine_rule import EngineRule

def generate_sarif_report(active_rules: list[EngineRule], findings: list[Finding]) -> dict:
    """Compile rules and findings into a SARIF report dict."""
    sarif_rules = []
    for r in active_rules:
        sarif_rules.append({
            "id": r.rule_code,
            "name": r.title,
            "shortDescription": {
                "text": r.title
            },
            "fullDescription": {
                "text": f"{r.what_is_wrong}\nCorrect way: {r.what_is_correct}"
            },
            "defaultConfiguration": {
                "level": "error" if r.severity == "error" else ("warning" if r.severity == "warning" else "note")
            }
        })
    
    sarif_results = []
    for finding in findings:
        region = {
            "startLine": finding.line,
            "endLine": finding.line
        }
        if finding.start_column is not None:
            region["startColumn"] = finding.start_column + 1
        if finding.end_column is not None:
            region["endColumn"] = finding.end_column + 1

        sarif_results.append({
            "ruleId": finding.rule_code,
            "message": {
                "text": f"{finding.title}: {finding.what_is_wrong}"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding.file_path
                        },
                        "region": region
                    }
                }
            ],
            "fingerprints": {
                "primaryLocationLineHash": finding.fingerprint
            }
        })

    sarif_data = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ReviewMind",
                        "semanticVersion": "1.0.0",
                        "rules": sarif_rules
                    }
                },
                "results": sarif_results
            }
        ]
    }
    return sarif_data
