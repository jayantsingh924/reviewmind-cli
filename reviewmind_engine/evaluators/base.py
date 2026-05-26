from abc import ABC, abstractmethod
from typing import Any
from reviewmind_engine.finding import Finding


class RuleEvaluator(ABC):
    """
    Base interface for all ReviewMind rule evaluators.
    Every evaluator receives a file and returns a list of Findings.

    Subclasses:
        RegexRuleEvaluator  — line-by-line pattern matching
        PythonASTRuleEvaluator — Python AST node traversal
        JavaScriptASTRuleEvaluator — JS/TS AST parsing
    """

    def __init__(self, rule: Any):
        self.rule = rule

    @abstractmethod
    def evaluate_file(
        self,
        filename: str,
        content: str,
        added_lines: set[int],
        context: dict | None = None,
    ) -> list[Finding]:
        """
        Scan a single file and return all matching findings.

        Args:
            filename:    Relative path of the file inside the repository.
            content:     Full file content as a string.
            added_lines: Set of 1-based line numbers that were added/modified
                         in this commit or PR diff.
            context:     Optional shared context dict. For Python files this
                         contains {"ast": <ast.Module>} pre-parsed once by
                         AnalysisEngine to avoid repeated compilation.

        Returns:
            List of Finding objects. Empty list if no violations found.
            """
        ...
