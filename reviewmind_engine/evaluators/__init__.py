from reviewmind_engine.evaluators.base import RuleEvaluator
from reviewmind_engine.evaluators.regex_evaluator import RegexRuleEvaluator
from reviewmind_engine.evaluators.python_ast_evaluator import PythonASTRuleEvaluator
from reviewmind_engine.evaluators.js_ast_evaluator import JavaScriptASTRuleEvaluator

def get_evaluator(rule) -> RuleEvaluator:
    # We support check_type="ast" and language python/javascript/typescript
    if getattr(rule, "check_type", None) == "ast":
        lang = getattr(rule, "check_language", "").lower()
        if lang == "python":
            return PythonASTRuleEvaluator(rule)
        elif lang in ("javascript", "typescript"):
            return JavaScriptASTRuleEvaluator(rule)
            
    # Default is regex evaluator
    return RegexRuleEvaluator(rule)
