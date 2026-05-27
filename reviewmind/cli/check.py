import os
import re
import subprocess
import sys
from pathlib import Path

import requests
import typer

from reviewmind.cli.cache import (
    flush_violations,
    get_cached_data,
    queue_violation,
    save_cached_data,
)
from reviewmind.cli.config import get_token
from reviewmind.cli.setup import get_git_repo_name
from reviewmind.engine import AnalysisEngine, EngineRule

API_BASE_URL = os.getenv("REVIEWMIND_API_URL", "http://localhost:8080/api")


def get_staged_changes():
    try:
        output = subprocess.check_output(["git", "diff", "--cached", "--unified=0"]).decode("utf-8")
        staged_lines = {}
        current_file = None
        hunk_regex = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

        for line in output.split("\n"):
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                staged_lines[current_file] = set()
            elif line.startswith("@@ ") and current_file:
                match = hunk_regex.match(line)
                if match:
                    start = int(match.group(1))
                    count = int(match.group(2)) if match.group(2) else 1
                    for line_idx in range(start, start + count):
                        staged_lines[current_file].add(line_idx)
        return staged_lines
    except Exception:
        return {}


def report_violation(project_id, rule_code, rule_id, commit_hash, file_path, line_number, token):
    if not project_id:
        queue_violation(None, rule_id, commit_hash, file_path, line_number)
        return

    url = f"{API_BASE_URL}/rules/{rule_id}/violations"
    headers = {"x-cli-token": token}
    payload = {"commit_hash": commit_hash, "file_path": file_path, "line_number": line_number}
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception:
        queue_violation(project_id, rule_id, commit_hash, file_path, line_number)


def apply_autofix(project_id, rule_id, file_path, line_number, token):
    if not project_id:
        typer.secho(
            "Auto-Fix is not available in standalone or offline mode.", fg=typer.colors.YELLOW
        )
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        typer.secho(f"Failed to read file: {e}", fg=typer.colors.RED)
        return False

    url = f"{API_BASE_URL}/rules/{rule_id}/autofix"
    headers = {"x-cli-token": token}
    payload = {"file_content": content, "line_number": line_number}

    try:
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok") and data.get("fixed_content"):
            fixed_code = data["fixed_content"]
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_code)
            subprocess.check_call(["git", "add", file_path])
            return True
        else:
            typer.secho("Backend failed to generate valid fix code.", fg=typer.colors.RED)
            return False
    except Exception as e:
        typer.secho(f"Auto-fix API error: {e}", fg=typer.colors.RED)
        return False


def run_check(
    fix: bool = False,
    rules_file: str | None = None,
    format_type: str = "console",
    output_file: str | None = None,
):
    token = None
    repo_name = None
    project_id = None
    rules_data = []
    is_offline = False
    is_standalone = False

    if rules_file:
        is_standalone = True
        rules_path = Path(rules_file)
        if not rules_path.exists():
            typer.secho(f"Error: Rules file not found at {rules_file}", fg=typer.colors.RED)
            raise typer.Exit(1)

        try:
            with open(rules_path, "r", encoding="utf-8") as rf:
                if rules_path.suffix in (".yml", ".yaml"):
                    import yaml

                    content = yaml.safe_load(rf)
                elif rules_path.suffix == ".json":
                    import json

                    content = json.load(rf)
                else:
                    typer.secho(
                        "Error: Rules file must be YAML (.yml/.yaml) or JSON (.json)",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(1)

                if isinstance(content, dict) and "rules" in content:
                    rules_data = content["rules"]
                elif isinstance(content, list):
                    rules_data = content
                else:
                    typer.secho(
                        "Error: Invalid rules format. "
                        "Must be a list of rules or have a 'rules' key.",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(1)

                from reviewmind.engine.validation import validate_rule

                validation_errors = []
                for idx, r_dict in enumerate(rules_data):
                    if not isinstance(r_dict, dict):
                        validation_errors.append(
                            f"Rule at index {idx} is not a valid JSON/YAML object."
                        )
                        continue
                    errors = validate_rule(r_dict)
                    if errors:
                        rule_code_str = r_dict.get("rule_code", f"index {idx}")
                        for err in errors:
                            validation_errors.append(f"Rule [{rule_code_str}]: {err}")

                if validation_errors:
                    typer.secho(
                        "Error: Local rules validation failed:", fg=typer.colors.RED, bold=True
                    )
                    for err in validation_errors:
                        typer.secho(f"  - {err}", fg=typer.colors.RED)
                    raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            typer.secho(f"Error reading rules file: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
    else:
        token = get_token()
        if not token:
            typer.secho(
                "Error: Not authenticated. Run 'reviewmind config add-authtoken <token>'",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        repo_name = get_git_repo_name()
        if not repo_name:
            typer.secho(
                "Error: Could not detect repository origin URL. Ensure you have a git remote.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        try:
            flush_violations(token)
        except Exception:
            pass

        headers = {"x-cli-token": token}

        try:
            resp = requests.get(
                f"{API_BASE_URL}/projects/lookup", params={"repo": repo_name}, headers=headers
            )
            if resp.status_code == 404:
                typer.secho(
                    f"Project '{repo_name}' not found in ReviewMind. Ensure you've registered it.",
                    fg=typer.colors.YELLOW,
                )
                raise typer.Exit(0)
            resp.raise_for_status()
            project = resp.json()
            project_id = project["id"]

            resp = requests.get(
                f"{API_BASE_URL}/projects/{project_id}/rules/active", headers=headers
            )
            resp.raise_for_status()
            rules_data = resp.json()

            save_cached_data(repo_name, project_id, rules_data)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            is_offline = True
            cached_data = get_cached_data(repo_name)
            project_id = cached_data.get("project_id")
            rules_data = cached_data.get("rules", [])

            if rules_data:
                typer.secho(
                    "\n[WARNING] ReviewMind backend offline. "
                    "Running check with locally cached rules...",
                    fg=typer.colors.YELLOW,
                    bold=True,
                )
            else:
                typer.secho(
                    "\n[WARNING] ReviewMind backend offline "
                    "and no local rules are cached for this project.",
                    fg=typer.colors.YELLOW,
                )
                raise typer.Exit(0)
        except typer.Exit:
            raise
        except Exception as e:
            typer.secho(f"API Error fetching rules: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)

    engine_rules = []
    rule_id_map = {}
    for r in rules_data:
        rule_obj = EngineRule.from_dict(r)
        engine_rules.append(rule_obj)
        rule_id_map[rule_obj.rule_code] = r.get("id")

    def clean_exit(exit_code: int, findings_list=None):
        if format_type.strip().lower() != "console" or output_file:
            from reviewmind.cli.exporters import export_findings

            export_findings(format_type, engine_rules, findings_list or [], output_file)
        raise typer.Exit(exit_code)

    if not rules_data:
        clean_exit(0, [])

    staged_changes = get_staged_changes()
    if not staged_changes:
        clean_exit(0, [])

    try:
        commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception:
        commit_hash = "unknown"

    import pathspec

    ignore_spec = None
    if Path(".reviewmind.yml").exists():
        try:
            import yaml

            with open(".reviewmind.yml", "r", encoding="utf-8") as yf:
                config_yml = yaml.safe_load(yf) or {}
                ignore_patterns = config_yml.get("ignore", [])
                if ignore_patterns:
                    ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)
        except Exception:
            pass

    files_to_scan = []
    for file_path, modified_lines in staged_changes.items():
        if not modified_lines:
            continue
        if not Path(file_path).exists():
            continue

        if ignore_spec and ignore_spec.match_file(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            continue

        files_to_scan.append(
            {"filename": file_path, "content": content, "added_lines": modified_lines}
        )

    if not files_to_scan:
        clean_exit(0, [])

    engine = AnalysisEngine(rules=engine_rules)
    findings = engine.run_scan(files_to_scan)

    if not findings:
        clean_exit(0, [])

    violations_found = False
    for finding in findings:
        violations_found = True

        # Only print individual findings if format is console
        if format_type.strip().lower() == "console":
            severity = finding.severity.upper()
            if severity in ("CRITICAL", "HIGH", "ERROR"):
                color = typer.colors.RED
            elif severity in ("MEDIUM", "WARNING"):
                color = typer.colors.YELLOW
            else:
                color = typer.colors.CYAN

            try:
                typer.secho(
                    f"\n[{severity}] Rule Violation in {finding.file_path}:{finding.line}",
                    fg=color,
                    bold=True,
                )
                typer.secho(f"Rule: {finding.title}")
                typer.secho(f"Found: {finding.normalized_content}")
                typer.secho(f"Fix: {finding.what_is_correct}\n")
            except UnicodeEncodeError:
                sys.stdout.write(
                    f"\n[{severity}] Rule Violation in {finding.file_path}:{finding.line}\n"
                )
                sys.stdout.write(f"Rule: {finding.title}\n")
                sys.stdout.write(f"Found: {finding.normalized_content}\n")
                sys.stdout.write(f"Fix: {finding.what_is_correct}\n\n")

        db_rule_id = rule_id_map.get(finding.rule_code)
        if db_rule_id and not is_standalone:
            report_violation(
                project_id,
                finding.rule_code,
                db_rule_id,
                commit_hash,
                finding.file_path,
                finding.line,
                token,
            )

        if not is_standalone and project_id and format_type.strip().lower() == "console":
            if fix or (
                sys.stdin.isatty()
                and typer.confirm("Would you like ReviewMind to auto-fix this file?", default=False)
            ):
                typer.secho("Applying AI Auto-Fix...", fg=typer.colors.BLUE)
                if apply_autofix(
                    project_id, db_rule_id or "unknown", finding.file_path, finding.line, token
                ):
                    typer.secho(
                        "AI Auto-Fix applied successfully! The file has been updated and restaged.",
                        fg=typer.colors.GREEN,
                    )
                    break

    if violations_found:
        if format_type.strip().lower() == "console":
            if is_offline:
                typer.secho(
                    "Commit blocked locally due to ReviewMind rule violations. "
                    "Violations queued to sync next time online.",
                    fg=typer.colors.RED,
                    bold=True,
                )
            else:
                typer.secho(
                    "Commit blocked due to ReviewMind rule violations.",
                    fg=typer.colors.RED,
                    bold=True,
                )
        clean_exit(1, findings)

    clean_exit(0, [])
