import os
import subprocess
import sys
from pathlib import Path

import requests
import typer

from reviewmind.cli.config import CONFIG_DIR, get_token

API_BASE_URL = os.getenv("REVIEWMIND_API_URL", "http://localhost:8080/api")


def check_python_version() -> bool:
    v = sys.version_info
    v_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 10):
        typer.secho(
            f"  ✓ Python version is {v_str} (compatible)",
            fg=typer.colors.GREEN,
        )
        return True
    else:
        typer.secho(
            f"  ✗ Python version is {v_str} (requires >= 3.10)",
            fg=typer.colors.RED,
        )
        return False


def check_git_repo() -> tuple[bool, Path | None]:
    try:
        is_git = (
            subprocess.check_output(
                ["git", "rev-parse", "--is-inside-work-tree"],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
        if is_git == "true":
            git_dir = (
                subprocess.check_output(
                    ["git", "rev-parse", "--git-dir"],
                    stderr=subprocess.DEVNULL,
                )
                .decode("utf-8")
                .strip()
            )
            typer.secho("  ✓ Current directory is inside a Git repository", fg=typer.colors.GREEN)
            return True, Path(git_dir)
    except Exception:
        pass

    typer.secho("  ✗ Not a Git repository (run in a git working directory)", fg=typer.colors.RED)
    return False, None


def check_precommit_hook(git_dir: Path | None, repair: bool = False) -> bool:
    if not git_dir:
        typer.secho("  - Skip pre-commit check (not a Git repo)", fg=typer.colors.YELLOW)
        return False

    hook_path = git_dir / "hooks" / "pre-commit"
    is_missing = not hook_path.exists()
    is_incorrect = False

    if not is_missing:
        try:
            content = hook_path.read_text(encoding="utf-8")
            if "reviewmind check" not in content:
                is_incorrect = True
        except Exception as e:
            typer.secho(f"  ✗ Error reading pre-commit hook: {e}", fg=typer.colors.RED)
            if repair:
                typer.secho("  Attempting to repair hook...", fg=typer.colors.BLUE)
                try:
                    from reviewmind.cli.setup import run_setup

                    run_setup()
                    typer.secho("  ✓ pre-commit hook successfully repaired!", fg=typer.colors.GREEN)
                    return True
                except Exception as ex:
                    typer.secho(f"  ✗ Failed to repair pre-commit hook: {ex}", fg=typer.colors.RED)
            return False

    if is_missing or is_incorrect:
        if is_missing:
            msg = "  ✗ pre-commit hook is not installed. Run 'reviewmind setup'"
        else:
            msg = (
                "  ✗ pre-commit hook exists but does not call 'reviewmind check'. "
                "Run 'reviewmind setup'"
            )

        if repair:
            typer.secho(msg, fg=typer.colors.YELLOW)
            typer.secho("  Attempting to repair hook...", fg=typer.colors.BLUE)
            try:
                from reviewmind.cli.setup import run_setup

                run_setup()
                typer.secho("  ✓ pre-commit hook successfully repaired!", fg=typer.colors.GREEN)
                return True
            except Exception as ex:
                typer.secho(f"  ✗ Failed to repair pre-commit hook: {ex}", fg=typer.colors.RED)
                return False
        else:
            typer.secho(msg, fg=typer.colors.RED)
            return False

    typer.secho("  ✓ pre-commit hook is installed and configured", fg=typer.colors.GREEN)
    return True


def check_auth() -> bool:
    token = get_token()
    if not token:
        typer.secho(
            "  ✗ Not authenticated. Run 'reviewmind login' "
            "or 'reviewmind config add-authtoken <token>'",
            fg=typer.colors.RED,
        )
        return False

    masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "..."
    typer.secho(f"  ✓ Authenticated with token: {masked}", fg=typer.colors.GREEN)
    return True


def check_cache_dir() -> bool:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        test_file = CONFIG_DIR / ".doctor_write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        typer.secho(
            f"  ✓ Configuration directory '{CONFIG_DIR}' is writable",
            fg=typer.colors.GREEN,
        )
        return True
    except Exception as e:
        typer.secho(
            f"  ✗ Configuration directory '{CONFIG_DIR}' is not writable: {e}",
            fg=typer.colors.RED,
        )
        return False


def check_backend_connection() -> bool:
    try:
        # Quick health ping to backend API base url
        resp = requests.get(API_BASE_URL, timeout=5)
        # 404 is okay (just means backend endpoint structure doesn't serve root),
        # but connection success is what we're testing.
        if resp.status_code in (200, 404, 403):
            typer.secho(
                f"  ✓ Successfully connected to ReviewMind backend ({API_BASE_URL})",
                fg=typer.colors.GREEN,
            )
            return True
    except Exception as e:
        typer.secho(
            f"  ✗ Failed to connect to ReviewMind backend ({API_BASE_URL}): {e}",
            fg=typer.colors.RED,
        )
    return False


def run_doctor(repair: bool = False):
    """Run diagnostics to verify CLI health and environment configuration."""
    typer.secho("ReviewMind Doctor - Diagnostic Tool\n", bold=True)

    issues = 0

    typer.secho("Environment Check:")
    if not check_python_version():
        issues += 1
    if not check_cache_dir():
        issues += 1

    typer.secho("\nGit Hook Check:")
    is_git, git_dir = check_git_repo()
    if not is_git:
        issues += 1
    elif not check_precommit_hook(git_dir, repair=repair):
        issues += 1

    typer.secho("\nAuthentication & Network Check:")
    if not check_auth():
        issues += 1
    if not check_backend_connection():
        issues += 1

    typer.secho("\nSummary:")
    if issues == 0:
        typer.secho(
            "✓ ReviewMind CLI is healthy and correctly configured!",
            fg=typer.colors.GREEN,
            bold=True,
        )
        raise typer.Exit(0)
    else:
        if repair:
            typer.secho(
                f"✗ Doctor completed repairs, but {issues} issue(s) still "
                "remain or cannot be auto-fixed.",
                fg=typer.colors.RED,
                bold=True,
            )
        else:
            typer.secho(
                f"✗ Doctor found {issues} configuration issue(s). Please fix "
                "the errors listed above or try running with --repair.",
                fg=typer.colors.RED,
                bold=True,
            )
        raise typer.Exit(1)
