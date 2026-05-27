import os
import time
import webbrowser

import requests
import typer

from reviewmind.cli.config import load_config, save_config

GITHUB_CLIENT_ID = os.getenv("REVIEWMIND_GITHUB_CLIENT_ID", "Ov23lieF35NEj0jkNWXw")

_DEVICE_CODE_URL = "https://github.com/login/device/code"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_REPOS_URL = "https://api.github.com/user/repos"


def _require_client_id() -> str:
    client_id = GITHUB_CLIENT_ID
    if not client_id:
        typer.secho(
            "Error: REVIEWMIND_GITHUB_CLIENT_ID is not set.\n"
            "\n"
            "To fix this:\n"
            "  1. Go to https://github.com/settings/developers\n"
            "  2. Click 'New OAuth App'\n"
            "  3. Enable 'Device authorization flow'\n"
            "  4. Copy the Client ID\n"
            "  5. Set it: export REVIEWMIND_GITHUB_CLIENT_ID=<your-client-id>\n",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    return client_id


def _poll_for_token(client_id: str, device_code: str, interval: int, expires_in: int) -> str:
    """Poll GitHub until the user approves or the code expires."""
    deadline = time.time() + expires_in
    current_interval = interval

    while time.time() < deadline:
        time.sleep(current_interval)

        resp = requests.post(
            _TOKEN_URL,
            json={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        data = resp.json()

        if "access_token" in data:
            return data["access_token"]

        error = data.get("error", "")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            current_interval += 5
        elif error in ("expired_token", "access_denied"):
            typer.secho(
                f"Authentication {error.replace('_', ' ')}. Please try again.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

    typer.secho("Authentication timed out. Please try again.", fg=typer.colors.RED)
    raise typer.Exit(1)


def _select_repo(github_token: str) -> str | None:
    """Fetch the user's repos and prompt them to pick one."""
    typer.echo("\nFetching your GitHub repositories...")

    repos = []
    page = 1
    while True:
        resp = requests.get(
            _REPOS_URL,
            params={"per_page": 100, "page": page, "sort": "pushed", "type": "all"},
            headers={"Authorization": f"Bearer {github_token}"},
            timeout=15,
        )
        batch = resp.json()
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    if not repos:
        typer.secho("No repositories found on your GitHub account.", fg=typer.colors.YELLOW)
        return None

    display = repos[:20]
    typer.echo("\nSelect the repository ReviewMind should enforce rules on:\n")
    for i, repo in enumerate(display, 1):
        typer.echo(f"  {i:2}. {repo['full_name']}")

    typer.echo()
    raw = typer.prompt("Enter number", default="1")

    try:
        idx = int(raw.strip()) - 1
        selected = display[idx]["full_name"]
        typer.secho(f"\n✓ Repository '{selected}' selected.", fg=typer.colors.GREEN, bold=True)
        return selected
    except (ValueError, IndexError):
        typer.secho("Invalid selection — skipping repo setup.", fg=typer.colors.YELLOW)
        return None


def run_login():
    """Authenticate the CLI via GitHub OAuth Device Flow."""
    client_id = _require_client_id()

    # Step 1 — request a device code
    resp = requests.post(
        _DEVICE_CODE_URL,
        json={"client_id": client_id, "scope": "read:user,repo"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data.get("verification_uri", "https://github.com/login/device")
    expires_in = data.get("expires_in", 900)
    interval = data.get("interval", 5)

    # Step 2 — show the code and open the browser
    typer.secho(
        f"\n  Your GitHub authentication code:  {user_code}\n",
        fg=typer.colors.CYAN,
        bold=True,
    )
    typer.echo(f"  Opening: {verification_uri}")
    typer.echo("  Enter the code above on GitHub to authorize ReviewMind.\n")

    try:
        webbrowser.open(verification_uri)
    except Exception:
        typer.secho(
            f"  Could not open browser automatically. Visit: {verification_uri}",
            fg=typer.colors.YELLOW,
        )

    typer.echo("Waiting for GitHub authorization...\n")

    # Step 3 — poll until approved
    github_token = _poll_for_token(client_id, device_code, interval, expires_in)

    # Step 4 — get GitHub user info
    user_resp = requests.get(
        _USER_URL,
        headers={"Authorization": f"Bearer {github_token}"},
        timeout=15,
    )
    user_resp.raise_for_status()
    user_data = user_resp.json()
    username = user_data.get("login", "unknown")

    typer.secho(f"✓ Authenticated as {username}!", fg=typer.colors.GREEN, bold=True)

    # Step 5 — repo selection
    selected_repo = _select_repo(github_token)

    # Step 6 — persist everything
    config_data = load_config()
    config_data["token"] = github_token
    config_data["github_username"] = username
    if selected_repo:
        config_data["selected_repo"] = selected_repo
    save_config(config_data)

    typer.secho(
        "\n✓ All set! Run 'reviewmind setup' in your project to install the pre-commit hook.",
        fg=typer.colors.CYAN,
        bold=True,
    )
