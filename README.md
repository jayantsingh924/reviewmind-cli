# ReviewMind CLI

> Enforce your team's code review rules **before** they reach GitHub.

ReviewMind turns recurring PR review comments into automated, enforceable rules.
This CLI runs those rules locally on your staged files before every commit —
catching violations before they ever open a pull request.

---

## How It Works

```
Your team writes a PR comment: "Don't use eval() — use safe_parse instead"
         ↓
ReviewMind extracts an enforceable rule (on the SaaS dashboard)
         ↓
Rule is approved by your team lead
         ↓
reviewmind CLI enforces it on every future commit — locally, instantly
```

---

## Installation

```bash
pip install reviewmind
```

Or with [pipx](https://pipx.pypa.io/):

```bash
pipx install reviewmind
```

---

## Quick Start

### 1. Authenticate with GitHub

```bash
reviewmind login
```

This opens `https://github.com/login/device` in your browser and shows a short code in the terminal.
Enter the code on GitHub, approve the app, and the CLI authenticates automatically — no tokens to copy or paste.

After approval you'll be prompted to pick which repository ReviewMind should enforce rules on.

### 2. Set up the pre-commit hook

```bash
cd your-project
reviewmind setup
```

Installs a pre-commit hook that automatically runs `reviewmind check` before every `git commit`.

### 3. Run a manual scan

```bash
reviewmind check
```

### 4. Verify your setup

```bash
reviewmind doctor
```

Checks authentication, backend connectivity, and config directory permissions.

---

## Example Output

```
ReviewMind scanning 3 staged files...

  src/auth.py
  ❌ [RM001] Dangerous Eval Usage — Line 12, Col 4
     Using eval() is dangerous. Use safe_parse_json() instead.

  src/utils.py
  ⚠️  [RM004] Direct Print Statement — Line 8
     Use the logger instead of print().

─────────────────────────────────────────────
2 violations found. Commit blocked.
Run `reviewmind check --fix` to apply AI suggestions.
```

---

## Engine — Open Source Core

This repository contains the **core scanning engine** used by both:
- This CLI (local pre-commit scanning)
- [ReviewMind SaaS](https://reviewmind.ai) (GitHub PR scanning)

### Engine Capabilities

| Feature | Status |
|---|---|
| Regex pattern matching | ✅ |
| Python AST scanning | ✅ |
| JavaScript / TypeScript AST | ✅ |
| SARIF export | ✅ |
| Ignore config (`.reviewmind.yml`) | ✅ |
| Column-precise highlights | ✅ |
| Fingerprint deduplication | ✅ |

### Using the engine directly

```python
from reviewmind import AnalysisEngine, EngineRule

rules = [
    EngineRule(
        rule_code="RM001",
        title="No eval()",
        check_type="regex",
        check_pattern=r"eval\(",
        check_language="python",
        severity="error",
        what_is_wrong="eval() is dangerous",
        what_is_correct="Use safe_parse_json()",
    )
]

engine = AnalysisEngine(rules=rules)

findings = engine.run_scan([
    {
        "filename": "src/main.py",
        "content": open("src/main.py").read(),
        "added_lines": {10, 11, 12},  # lines changed in this commit
    }
])

for f in findings:
    print(f"{f.rule_code} | {f.file_path}:{f.line} | {f.message}")
```

---

## Configuration

Create `.reviewmind.yml` in your repo root to ignore paths:

```yaml
ignore:
  - "tests/**"
  - "migrations/**"
  - "generated/**"
  - "*.min.js"
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REVIEWMIND_API_URL` | `http://localhost:8080/api` | Backend API URL |
| `REVIEWMIND_GITHUB_CLIENT_ID` | *(bundled)* | Override the GitHub OAuth App client ID |

Authentication is handled via GitHub OAuth Device Flow during `reviewmind login`.
The GitHub token is stored in `~/.reviewmind/config.json` and sent as the `x-cli-token` header in all API requests.

---

## Contributing

Contributions are welcome! This is the open source engine — feel free to:
- Add new language evaluators
- Improve AST detection patterns
- Fix bugs and improve test coverage

```bash
git clone https://github.com/jayantsingh924/reviewmind-cli
cd reviewmind-cli
pip install -e ".[dev]"
pytest
```

---

## License

MIT — see [LICENSE](LICENSE)

---

## Links

- 🌐 [ReviewMind SaaS Platform](https://reviewmind.ai) — Full dashboard, GitHub App, team management
- 📖 [Documentation](https://docs.reviewmind.ai)
- 🐛 [Issue Tracker](https://github.com/jayantsingh924/reviewmind-cli/issues)
