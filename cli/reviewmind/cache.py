import json
import os
from pathlib import Path

import requests
import typer

CACHE_DIR = Path.home() / ".reviewmind"
RULES_CACHE_FILE = CACHE_DIR / "rules_cache.json"
QUEUE_FILE = CACHE_DIR / "violation_queue.json"

API_BASE_URL = os.getenv("REVIEWMIND_API_URL", "http://localhost:8080/api")


def load_json_file(file_path):
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json_file(file_path, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def get_cached_data(repo_name):
    cache = load_json_file(RULES_CACHE_FILE)
    return cache.get(str(repo_name), {"project_id": None, "rules": []})


def save_cached_data(repo_name, project_id, rules):
    cache = load_json_file(RULES_CACHE_FILE)
    cache[str(repo_name)] = {"project_id": str(project_id), "rules": rules}
    save_json_file(RULES_CACHE_FILE, cache)


def queue_violation(project_id, rule_id, commit_hash, file_path, line_number):
    queue = load_json_file(QUEUE_FILE)
    if "violations" not in queue:
        queue["violations"] = []

    violation = {
        "project_id": str(project_id) if project_id else None,
        "rule_id": str(rule_id),
        "commit_hash": commit_hash,
        "file_path": file_path,
        "line_number": line_number,
    }
    queue["violations"].append(violation)
    save_json_file(QUEUE_FILE, queue)


def flush_violations(token):
    queue = load_json_file(QUEUE_FILE)
    violations = queue.get("violations", [])
    if not violations:
        return

    typer.secho(
        f"Syncing {len(violations)} offline violations with ReviewMind...", fg=typer.colors.BLUE
    )
    headers = {"x-cli-token": token}

    remaining_violations = []
    for v in violations:
        url = f"{API_BASE_URL}/rules/{v['rule_id']}/violations"
        payload = {
            "commit_hash": v["commit_hash"],
            "file_path": v["file_path"],
            "line_number": v["line_number"],
        }
        try:
            resp = requests.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        except Exception:
            remaining_violations.append(v)

    if remaining_violations:
        queue["violations"] = remaining_violations
        save_json_file(QUEUE_FILE, queue)
        typer.secho(
            f"Failed to sync {len(remaining_violations)} violations. Retrying next time.",
            fg=typer.colors.YELLOW,
        )
    else:
        save_json_file(QUEUE_FILE, {"violations": []})
        typer.secho("All offline violations successfully synced!", fg=typer.colors.GREEN)
