import dataclasses
import json
import sys
from pathlib import Path

from reviewmind.engine.exporters.sarif_exporter import generate_sarif_report
from reviewmind.engine.finding import Finding


def generate_json_report(findings: list[Finding]) -> str:
    """Serialize findings to a JSON formatted string."""
    findings_dicts = [dataclasses.asdict(f) for f in findings]
    return json.dumps(findings_dicts, indent=4)


def generate_markdown_report(findings: list[Finding]) -> str:
    """Generate a clean, readable Markdown report from findings."""
    md = []
    md.append("# ReviewMind Scan Report\n")
    md.append(f"Total violations found: **{len(findings)}**\n")

    # Table summary
    md.append("| Rule Code | Severity | File | Line | Title |")
    md.append("|---|---|---|---|---|")
    for f in findings:
        md.append(
            f"| `{f.rule_code}` | **{f.severity.upper()}** | "
            f"`{f.file_path}` | {f.line} | {f.title} |"
        )
    md.append("\n## Detailed Findings\n")

    for i, f in enumerate(findings, 1):
        md.append(f"### {i}. [{f.severity.upper()}] {f.title} (`{f.rule_code}`)")
        md.append(f"- **Location**: `{f.file_path}:{f.line}`")
        md.append(f"- **What is wrong**: {f.what_is_wrong}")
        md.append(f"- **Recommended correction**: `{f.what_is_correct}`")
        if f.normalized_content:
            md.append("\n**Violating Code snippet:**")
            md.append("```")
            md.append(f.normalized_content.strip())
            md.append("```")
        if f.remediation:
            md.append(f"\n**Remediation Steps**: {f.remediation}")
        md.append("\n---")

    return "\n".join(md)


def export_findings(
    format_type: str,
    active_rules: list,
    findings: list[Finding],
    output_path: str | None = None,
) -> None:
    """Format and export findings to stdout or a file."""
    fmt = format_type.strip().lower()

    if fmt == "json":
        report_str = generate_json_report(findings)
    elif fmt == "markdown" or fmt == "md":
        report_str = generate_markdown_report(findings)
    elif fmt == "sarif":
        sarif_dict = generate_sarif_report(active_rules, findings)
        report_str = json.dumps(sarif_dict, indent=4)
    else:
        # Default to raw text summary (or console style)
        lines = []
        for f in findings:
            lines.append(
                f"[{f.severity.upper()}] {f.rule_code} in {f.file_path}:{f.line}\n"
                f"  Rule: {f.title}\n"
                f"  Found: {f.normalized_content.strip() if f.normalized_content else ''}\n"
                f"  Fix: {f.what_is_correct}\n"
            )
        report_str = "\n".join(lines)

    if output_path:
        out_p = Path(output_path)
        # Create parent directories if they don't exist
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(report_str, encoding="utf-8")
    else:
        sys.stdout.write(report_str + "\n")
