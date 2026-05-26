import ast
import re

from reviewmind_engine.evaluators.base import RuleEvaluator
from reviewmind_engine.finding import Finding


class PythonASTRuleEvaluator(RuleEvaluator):
    def evaluate_file(
        self, filename: str, content: str, added_lines: set[int], context: dict | None = None
    ) -> list[Finding]:
        if not filename.endswith(".py"):
            return []

        tree = None
        if context and "ast" in context:
            tree = context["ast"]

        if tree is None:
            try:
                tree = ast.parse(content)
            except Exception:
                return []

        findings = []

        class CallVisitor(ast.NodeVisitor):
            def __init__(self, target_name):
                self.target_name = target_name
                self.matches = []

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == self.target_name:
                    self.matches.append(node)
                elif isinstance(node.func, ast.Attribute) and node.func.attr == self.target_name:
                    self.matches.append(node)
                self.generic_visit(node)

        if self.rule.check_pattern:
            visitor = CallVisitor(self.rule.check_pattern)
            visitor.visit(tree)

            file_lines = content.splitlines()
            for node in visitor.matches:
                line_num = getattr(node, "lineno", 1)
                col_offset = getattr(node, "col_offset", None)
                end_col_offset = getattr(node, "end_col_offset", col_offset)

                if line_num in added_lines:
                    line_content = (
                        file_lines[line_num - 1] if line_num - 1 < len(file_lines) else ""
                    )
                    findings.append(
                        Finding(
                            rule_code=self.rule.rule_code,
                            title=self.rule.title,
                            message=(
                                f"Rule Violation (AST): {self.rule.rule_code} - {self.rule.title}\n"
                                f"{self.rule.what_is_wrong}\n"
                                f"Correct way: {self.rule.what_is_correct}"
                            ),
                            line=line_num,
                            what_is_wrong=self.rule.what_is_wrong,
                            what_is_correct=self.rule.what_is_correct,
                            severity=self.rule.severity,
                            file_path=filename,
                            normalized_content=re.sub(r"\s+", " ", line_content).strip(),
                            engine="ast",
                            start_column=col_offset,
                            end_column=end_col_offset,
                            symbol=self.rule.check_pattern,
                            category=(
                                "security"
                                if "secure" in self.rule.title.lower()
                                or "eval" in self.rule.title.lower()
                                else "style"
                            ),
                            remediation=self.rule.what_is_correct,
                            confidence=self.rule.confidence,
                        )
                    )
        return findings
