import webbrowser

import typer

from reviewmind.cli.config import load_config, save_config


def run_login():
    """Authenticate the CLI with ReviewMind via GitHub OAuth flow."""
    typer.echo("Opening browser for ReviewMind authentication...")

    auth_url = "https://reviewmind.ai/cli/auth"
    try:
        webbrowser.open(auth_url)
    except Exception:
        typer.secho(
            f"Failed to open browser automatically. Please open this URL: {auth_url}",
            fg=typer.colors.YELLOW,
        )

    typer.echo("\nWaiting for authentication in browser...")

    token = typer.prompt("Paste the CLI Token displayed in your browser").strip()

    if token:
        if not token.startswith("rm_live_"):
            typer.secho(
                "Warning: token does not start with rm_live_. It may be invalid.",
                fg=typer.colors.YELLOW,
            )
        config_data = load_config()
        config_data["token"] = token
        save_config(config_data)

        typer.secho(
            "✓ Successfully authenticated! Your CLI token has been saved.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho("Error: No token was provided.", fg=typer.colors.RED)
        raise typer.Exit(1)
