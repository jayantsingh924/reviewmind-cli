import typer

from cli.reviewmind import check, config, setup

app = typer.Typer(help="ReviewMind CLI to enforce AI-extracted PR rules")

app.add_typer(config.app, name="config", help="Manage configuration and auth tokens")


@app.command(name="setup")
def setup_command():
    """Set up the ReviewMind pre-commit hook in this repository."""
    setup.run_setup()


@app.command(name="check")
def check_command(
    fix: bool = typer.Option(False, "--fix", help="Automatically apply AI suggestions"),
    rules: str = typer.Option(None, "--rules", help="Path to a local rules file (YAML or JSON)"),
):
    """Check staged files against active rules (used by pre-commit hook)."""
    check.run_check(fix=fix, rules_file=rules)


if __name__ == "__main__":
    app()
