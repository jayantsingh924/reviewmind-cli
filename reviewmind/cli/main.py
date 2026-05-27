import typer

from reviewmind.cli import auth, check, config, doctor, setup

app = typer.Typer(help="ReviewMind CLI to enforce AI-extracted PR rules")

app.add_typer(config.app, name="config", help="Manage configuration and auth tokens")


@app.command(name="login")
def login_command():
    """Authenticate with GitHub using OAuth Flow."""
    auth.run_login()


@app.command(name="doctor")
def doctor_command():
    """Run diagnostics to verify CLI health and environment configuration."""
    doctor.run_doctor()


@app.command(name="setup")
def setup_command():
    """Set up the ReviewMind pre-commit hook in this repository."""
    setup.run_setup()


@app.command(name="check")
def check_command(
    fix: bool = typer.Option(False, "--fix", help="Automatically apply AI suggestions"),
    rules: str = typer.Option(None, "--rules", help="Path to a local rules file (YAML or JSON)"),
    format: str = typer.Option(
        "console", "--format", help="Output format: console, json, markdown, sarif"
    ),
    output: str = typer.Option(
        None, "--output", help="Write report to this file path instead of stdout"
    ),
):
    """Check staged files against active rules (used by pre-commit hook)."""
    check.run_check(fix=fix, rules_file=rules, format_type=format, output_file=output)


if __name__ == "__main__":
    app()
