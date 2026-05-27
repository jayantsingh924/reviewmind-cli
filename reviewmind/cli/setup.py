import os
import subprocess
from pathlib import Path

import typer

from reviewmind.cli.config import get_selected_repo, get_token

HOOK_SCRIPT = """#!/usr/bin/env bash

# ReviewMind Pre-Commit Hook
# Dynamically runs the reviewmind check command

reviewmind check
if [ $? -ne 0 ]; then
    echo "ReviewMind checks failed. Commit aborted."
    exit 1
fi

exit 0
"""


def get_git_repo_name():
    try:
        output = (
            subprocess.check_output(["git", "config", "--get", "remote.origin.url"])
            .decode("utf-8")
            .strip()
        )
        if output.endswith(".git"):
            output = output[:-4]
        if ":" in output and not output.startswith("http"):
            parts = output.split(":", 1)
            return parts[1]
        elif output.startswith("http"):
            parts = output.split("/")
            return f"{parts[-2]}/{parts[-1]}"
        return None
    except Exception:
        return None


def run_setup():
    token = get_token()
    if not token:
        typer.secho(
            "Error: Not authenticated. Please run 'reviewmind login' "
            "or 'reviewmind config add-authtoken <token>' first.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if not Path(".git").exists():
        typer.secho(
            "Error: Not a git repository. Run this command at the root of a git repo.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    repo_name = get_git_repo_name() or get_selected_repo()
    if not repo_name:
        typer.secho(
            "Warning: Could not detect repository. Run 'reviewmind login' to select one.",
            fg=typer.colors.YELLOW,
        )

    hooks_dir = Path(".git/hooks")
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit_file = hooks_dir / "pre-commit"

    with open(pre_commit_file, "w") as f:
        f.write(HOOK_SCRIPT)

    # Make it executable (mac/linux)
    if os.name != "nt":
        os.chmod(pre_commit_file, 0o755)

    typer.secho("Successfully installed ReviewMind pre-commit hook!", fg=typer.colors.GREEN)
    if repo_name:
        typer.secho(f"Repository detected as: {repo_name}", fg=typer.colors.BLUE)
