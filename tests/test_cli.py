import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from reviewmind.cli.check import run_check


def test_run_check_standalone_no_violations(tmp_path):
    rules_file = tmp_path / "rules.json"
    rules_data = {
        "rules": [
            {
                "rule_code": "RM001",
                "title": "No eval()",
                "check_type": "regex",
                "check_pattern": "eval\\(",
                "check_language": "python",
                "severity": "error",
                "what_is_wrong": "eval is dangerous",
                "what_is_correct": "use safe_parse",
            }
        ]
    }
    rules_file.write_text(json.dumps(rules_data))

    # Create dummy scan file
    scan_file = tmp_path / "app.py"
    scan_file.write_text("print('hello')\n")

    staged_changes = {str(scan_file): {1}}

    with patch("reviewmind.cli.check.get_staged_changes", return_value=staged_changes):
        # Should complete by raising Exit(0), meaning 0 violations
        with pytest.raises(typer.Exit) as exc_info:
            run_check(fix=False, rules_file=str(rules_file))
        assert exc_info.value.exit_code == 0


def test_run_check_standalone_with_violations(tmp_path):
    rules_file = tmp_path / "rules.json"
    rules_data = {
        "rules": [
            {
                "rule_code": "RM001",
                "title": "No eval()",
                "check_type": "regex",
                "check_pattern": "eval\\(",
                "check_language": "python",
                "severity": "error",
                "what_is_wrong": "eval is dangerous",
                "what_is_correct": "use safe_parse",
            }
        ]
    }
    rules_file.write_text(json.dumps(rules_data))

    # Create dummy scan file
    scan_file = tmp_path / "app.py"
    scan_file.write_text("eval('import os')\n")

    staged_changes = {str(scan_file): {1}}

    with (
        patch("reviewmind.cli.check.get_staged_changes", return_value=staged_changes),
        patch("typer.secho") as mock_secho,
    ):
        with pytest.raises(typer.Exit) as exc_info:
            run_check(fix=False, rules_file=str(rules_file))

        assert exc_info.value.exit_code == 1

        # Verify it does not mention "Violations queued to sync next time online"
        calls = [call[0][0] for call in mock_secho.call_args_list]
        queued_mention = any("queued to sync" in c for c in calls)
        assert not queued_mention, f"Queued mention should not be printed, but got calls: {calls}"

        blocked_mention = any(
            "Commit blocked due to ReviewMind rule violations." in c for c in calls
        )
        assert blocked_mention, f"Should mention blocked commit, but got calls: {calls}"


def test_run_check_rules_file_not_found():
    with pytest.raises(typer.Exit) as exc_info:
        run_check(fix=False, rules_file="non_existent_file.yaml")
    assert exc_info.value.exit_code == 1


@patch("reviewmind.cli.auth.webbrowser.open")
@patch("reviewmind.cli.auth.save_config")
@patch("reviewmind.cli.auth.load_config", return_value={})
@patch("reviewmind.cli.auth.typer.prompt", return_value="1")
@patch("reviewmind.cli.auth.requests.get")
@patch("reviewmind.cli.auth.requests.post")
def test_login_success(mock_post, mock_get, mock_prompt, mock_load_config, mock_save_config, mock_open):
    from unittest.mock import MagicMock
    from reviewmind.cli.auth import run_login

    # First post: device code request
    device_resp = MagicMock()
    device_resp.json.return_value = {
        "device_code": "test_device_code",
        "user_code": "ABCD-1234",
        "verification_uri": "https://github.com/login/device",
        "expires_in": 900,
        "interval": 1,
    }
    # Second post: token poll — approved immediately
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "gho_testtoken123"}
    mock_post.side_effect = [device_resp, token_resp]

    # First get: user info; second get: repo list
    user_resp = MagicMock()
    user_resp.json.return_value = {"login": "testuser"}
    repos_resp = MagicMock()
    repos_resp.json.return_value = [{"full_name": "testuser/my-repo"}]
    mock_get.side_effect = [user_resp, repos_resp]

    run_login()

    mock_open.assert_called_once_with("https://github.com/login/device")
    saved = mock_save_config.call_args[0][0]
    assert saved["token"] == "gho_testtoken123"
    assert saved["github_username"] == "testuser"
    assert saved["selected_repo"] == "testuser/my-repo"


@patch("reviewmind.cli.auth.requests.post")
def test_login_access_denied(mock_post):
    from unittest.mock import MagicMock
    from reviewmind.cli.auth import run_login

    device_resp = MagicMock()
    device_resp.json.return_value = {
        "device_code": "test_device_code",
        "user_code": "ABCD-1234",
        "verification_uri": "https://github.com/login/device",
        "expires_in": 900,
        "interval": 1,
    }
    denied_resp = MagicMock()
    denied_resp.json.return_value = {"error": "access_denied"}
    mock_post.side_effect = [device_resp, denied_resp]

    with patch("reviewmind.cli.auth.webbrowser.open"):
        with pytest.raises(typer.Exit) as exc_info:
            run_login()
    assert exc_info.value.exit_code == 1


def test_login_no_client_id():
    from reviewmind.cli.auth import _require_client_id
    import reviewmind.cli.auth as auth_module

    original = auth_module.GITHUB_CLIENT_ID
    auth_module.GITHUB_CLIENT_ID = ""
    try:
        with pytest.raises(typer.Exit) as exc_info:
            _require_client_id()
        assert exc_info.value.exit_code == 1
    finally:
        auth_module.GITHUB_CLIENT_ID = original


# --- Doctor tests ---
@patch("reviewmind.cli.doctor.requests.get")
@patch("reviewmind.cli.doctor.check_git_repo")
@patch("reviewmind.cli.doctor.get_token", return_value="rm_live_12345")
@patch("reviewmind.cli.doctor.check_cache_dir", return_value=True)
def test_doctor_success(mock_cache, mock_get_token, mock_git_repo, mock_get):
    from unittest.mock import MagicMock

    from reviewmind.cli.doctor import run_doctor

    # Mock git repo checking
    mock_git_repo.return_value = (True, Path("/fake/git"))

    # Mock precommit hook check inside test_cli
    with patch("reviewmind.cli.doctor.check_precommit_hook", return_value=True):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        with pytest.raises(typer.Exit) as exc_info:
            run_doctor()
        assert exc_info.value.exit_code == 0


@patch("reviewmind.cli.doctor.requests.get", side_effect=Exception("Timeout"))
@patch("reviewmind.cli.doctor.check_git_repo")
@patch("reviewmind.cli.doctor.get_token", return_value=None)
@patch("reviewmind.cli.doctor.check_cache_dir", return_value=True)
def test_doctor_failure(mock_cache, mock_get_token, mock_git_repo, mock_get):
    from reviewmind.cli.doctor import run_doctor

    mock_git_repo.return_value = (False, None)
    with pytest.raises(typer.Exit) as exc_info:
        run_doctor()
    assert exc_info.value.exit_code == 1


# --- Rule Validation tests ---
def test_normalize_severity():
    from reviewmind.engine.validation import normalize_severity

    assert normalize_severity("error") == "HIGH"
    assert normalize_severity("WARNING") == "MEDIUM"
    assert normalize_severity("info") == "INFO"
    assert normalize_severity("CRITICAL") == "CRITICAL"
    assert normalize_severity(None) == "HIGH"
    assert normalize_severity("invalid") == "HIGH"


def test_validate_rule():
    from reviewmind.engine.validation import validate_rule

    valid = {
        "rule_code": "RM999",
        "title": "Good rule",
        "check_type": "regex",
        "check_pattern": "test",
        "check_language": "python",
        "what_is_wrong": "bad",
        "what_is_correct": "good",
    }
    assert validate_rule(valid) == []

    invalid_missing = {
        "rule_code": "RM999",
        "title": "Good rule",
        "check_type": "regex",
    }
    errs = validate_rule(invalid_missing)
    assert len(errs) > 0
    assert any("check_language" in e for e in errs)

    invalid_regex = {
        "rule_code": "RM999",
        "title": "Good rule",
        "check_type": "regex",
        "check_pattern": "[invalid regex",
        "check_language": "python",
        "what_is_wrong": "bad",
        "what_is_correct": "good",
    }
    errs2 = validate_rule(invalid_regex)
    assert len(errs2) == 1
    assert "Invalid regex check_pattern" in errs2[0]


# --- Exporters tests ---
def test_check_exporters_json(tmp_path):
    rules_file = tmp_path / "rules.json"
    rules_data = {
        "rules": [
            {
                "rule_code": "RM001",
                "title": "No eval()",
                "check_type": "regex",
                "check_pattern": "eval\\(",
                "check_language": "python",
                "severity": "CRITICAL",
                "what_is_wrong": "eval is dangerous",
                "what_is_correct": "use safe_parse",
            }
        ]
    }
    rules_file.write_text(json.dumps(rules_data))

    # Create dummy scan file
    scan_file = tmp_path / "app.py"
    scan_file.write_text("eval('import os')\n")
    staged_changes = {str(scan_file): {1}}

    output_json_file = tmp_path / "report.json"

    with patch("reviewmind.cli.check.get_staged_changes", return_value=staged_changes):
        with pytest.raises(typer.Exit) as exc_info:
            run_check(
                fix=False,
                rules_file=str(rules_file),
                format_type="json",
                output_file=str(output_json_file),
            )
        assert exc_info.value.exit_code == 1

    assert output_json_file.exists()
    report = json.loads(output_json_file.read_text(encoding="utf-8"))
    assert len(report) == 1
    assert report[0]["rule_code"] == "RM001"
    assert report[0]["severity"] == "CRITICAL"
