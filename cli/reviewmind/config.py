import json
from pathlib import Path

import typer

app = typer.Typer()

CONFIG_DIR = Path.home() / ".reviewmind"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config_data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)


@app.command()
def add_authtoken(token: str = typer.Argument(..., help="Your rm_live_... CLI token")):
    """Save the authentication token."""
    if not token.startswith("rm_live_"):
        typer.secho(
            "Warning: token does not start with rm_live_. It may be invalid.",
            fg=typer.colors.YELLOW,
        )

    config_data = load_config()
    config_data["token"] = token
    save_config(config_data)

    typer.secho(f"Token saved to {CONFIG_FILE}", fg=typer.colors.GREEN)


def get_token():
    config_data = load_config()
    return config_data.get("token")
