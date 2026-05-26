from unittest.mock import MagicMock

from reviewmind_engine.analysis_engine import AnalysisEngine
from reviewmind_engine.finding import Finding


def make_rule(
    rule_code="RM001",
    title="Test Rule",
    check_type="regex",
    check_pattern=r"eval\(",
    check_language="python",
    severity="error",
    supports_autofix=False,
    supports_ast=False,
    requires_language=None,
    what_is_wrong="Using eval() is dangerous.",
    what_is_correct="Use safe_parse_json() instead.",
    confidence=0.9,
):
    rule = MagicMock()
    rule.rule_code = rule_code
    rule.title = title
    rule.check_type = check_type
    rule.check_pattern = check_pattern
    rule.check_language = check_language
    rule.severity = severity
    rule.supports_autofix = supports_autofix
    rule.supports_ast = supports_ast
    rule.requires_language = requires_language
    rule.what_is_wrong = what_is_wrong
    rule.what_is_correct = what_is_correct
    rule.confidence = confidence
    return rule


# -------------------------------------------------------------------
# Finding dataclass
# -------------------------------------------------------------------


def test_finding_fields():
    f = Finding(
        rule_code="RM001",
        title="Eval Usage",
        message="Do not use eval()",
        line=10,
        what_is_wrong="eval is dangerous",
        what_is_correct="use safe_parse",
        severity="error",
        file_path="src/main.py",
        normalized_content="x = eval(data)",
        suggestion=None,
        engine="regex",
        start_column=4,
        end_column=8,
        symbol="eval",
        category="security",
        remediation="Replace eval with safe_parse_json",
        confidence=0.95,
    )
    assert f.rule_code == "RM001"
    assert f.line == 10
    assert f.engine == "regex"


def test_finding_fingerprint_is_stable():
    """Fingerprint must not change when only line number changes."""
    f1 = Finding(
        rule_code="RM001",
        title="T",
        message="M",
        line=5,
        what_is_wrong="W",
        what_is_correct="C",
        severity="error",
        file_path="src/a.py",
        normalized_content="  x = eval(data)  ",
        suggestion=None,
        engine="regex",
        start_column=None,
        end_column=None,
        symbol=None,
        category=None,
        remediation=None,
        confidence=0.9,
    )
    f2 = Finding(
        rule_code="RM001",
        title="T",
        message="M",
        line=99,
        what_is_wrong="W",
        what_is_correct="C",
        severity="error",
        file_path="src/a.py",
        normalized_content="  x = eval(data)  ",
        suggestion=None,
        engine="regex",
        start_column=None,
        end_column=None,
        symbol=None,
        category=None,
        remediation=None,
        confidence=0.9,
    )
    assert f1.fingerprint == f2.fingerprint


# -------------------------------------------------------------------
# Regex Evaluator
# -------------------------------------------------------------------


def test_regex_evaluator_detects_violation():
    from reviewmind_engine.evaluators.regex_evaluator import RegexRuleEvaluator

    rule = make_rule(check_type="regex", check_pattern=r"eval\(")
    ev = RegexRuleEvaluator(rule)
    findings = ev.evaluate_file(
        filename="src/main.py",
        content="x = 1\ny = eval(data)\nz = 3\n",
        added_lines={2},
    )
    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].rule_code == "RM001"


def test_regex_evaluator_skips_non_added_lines():
    from reviewmind_engine.evaluators.regex_evaluator import RegexRuleEvaluator

    rule = make_rule(check_type="regex", check_pattern=r"eval\(")
    ev = RegexRuleEvaluator(rule)
    findings = ev.evaluate_file(
        filename="src/main.py",
        content="x = eval(data)\n",
        added_lines={99},  # line 1 not in added_lines
    )
    assert findings == []


def test_regex_evaluator_no_match():
    from reviewmind_engine.evaluators.regex_evaluator import RegexRuleEvaluator

    rule = make_rule(check_type="regex", check_pattern=r"eval\(")
    ev = RegexRuleEvaluator(rule)
    findings = ev.evaluate_file(
        filename="src/main.py",
        content="x = safe_parse(data)\n",
        added_lines={1},
    )
    assert findings == []


# -------------------------------------------------------------------
# Python AST Evaluator
# -------------------------------------------------------------------


def test_python_ast_evaluator_detects_eval():
    import ast

    from reviewmind_engine.evaluators.python_ast_evaluator import PythonASTRuleEvaluator

    rule = make_rule(
        check_type="ast",
        check_pattern="eval",
        check_language="python",
        supports_ast=True,
    )
    ev = PythonASTRuleEvaluator(rule)
    content = "def foo():\n    result = eval(user_input)\n"
    tree = ast.parse(content)
    findings = ev.evaluate_file(
        filename="src/foo.py",
        content=content,
        added_lines={2},
        context={"ast": tree},
    )
    assert len(findings) == 1
    assert findings[0].symbol == "eval"
    assert findings[0].engine == "ast"


def test_python_ast_evaluator_skips_non_added_lines():
    import ast

    from reviewmind_engine.evaluators.python_ast_evaluator import PythonASTRuleEvaluator

    rule = make_rule(check_type="ast", check_pattern="eval", supports_ast=True)
    ev = PythonASTRuleEvaluator(rule)
    content = "result = eval(data)\n"
    tree = ast.parse(content)
    findings = ev.evaluate_file(
        filename="src/foo.py",
        content=content,
        added_lines={99},
        context={"ast": tree},
    )
    assert findings == []


# -------------------------------------------------------------------
# Analysis Engine — integration
# -------------------------------------------------------------------


def test_analysis_engine_shared_ast_parse():
    """Engine must parse Python AST only once even with multiple AST rules."""
    rule1 = make_rule("RM001", check_type="ast", check_pattern="eval", supports_ast=True)
    rule2 = make_rule("RM002", check_type="ast", check_pattern="exec", supports_ast=True)
    engine = AnalysisEngine(rules=[rule1, rule2])

    files = [
        {
            "filename": "src/main.py",
            "content": "eval(x)\nexec(y)\n",
            "added_lines": {1, 2},
        }
    ]
    findings = engine.run_scan(files)
    rule_codes = {f.rule_code for f in findings}
    assert "RM001" in rule_codes
    assert "RM002" in rule_codes


def test_analysis_engine_language_filter():
    """Rules for python must not fire on .js files."""
    rule = make_rule("RM001", check_type="regex", check_pattern=r"eval\(", check_language="python")
    engine = AnalysisEngine(rules=[rule])
    files = [
        {
            "filename": "src/app.js",
            "content": "eval(data);\n",
            "added_lines": {1},
        }
    ]
    findings = engine.run_scan(files)
    assert findings == []


def test_analysis_engine_empty_added_lines():
    """Files with no added lines produce no findings."""
    rule = make_rule("RM001", check_type="regex", check_pattern=r"eval\(")
    engine = AnalysisEngine(rules=[rule])
    files = [
        {
            "filename": "src/main.py",
            "content": "eval(data)\n",
            "added_lines": set(),
        }
    ]
    findings = engine.run_scan(files)
    assert findings == []
