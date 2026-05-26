import re

from reviewmind_engine.evaluators.base import RuleEvaluator
from reviewmind_engine.finding import Finding


class JavaScriptASTRuleEvaluator(RuleEvaluator):
    def evaluate_file(
        self, filename: str, content: str, added_lines: set[int], context: dict | None = None
    ) -> list[Finding]:
        if not (
            filename.endswith(".js")
            or filename.endswith(".jsx")
            or filename.endswith(".ts")
            or filename.endswith(".tsx")
        ):
            return []

        findings = []
        if not self.rule.check_pattern:
            return []

        target = self.rule.check_pattern
        pattern = re.compile(rf"\b{re.escape(target)}\s*\(")

        lines = content.splitlines()
        for i, line in enumerate(lines, start=1):
            if i not in added_lines:
                continue

            for match in pattern.finditer(line):
                start_col = match.start()
                open_paren_idx = line.find("(", start_col)
                if open_paren_idx != -1:
                    paren_count = 1
                    end_col = open_paren_idx + 1
                    while end_col < len(line) and paren_count > 0:
                        if line[end_col] == "(":
                            paren_count += 1
                        elif line[end_col] == ")":
                            paren_count -= 1
                        end_col += 1
                else:
                    end_col = match.end()

                findings.append(
                    Finding(
                        rule_code=self.rule.rule_code,
                        title=self.rule.title,
                        message=(
                            f"Rule Violation (AST): {self.rule.rule_code} - {self.rule.title}\n"
                            f"{self.rule.what_is_wrong}\n"
                            f"Correct way: {self.rule.what_is_correct}"
                        ),
                        line=i,
                        what_is_wrong=self.rule.what_is_wrong,
                        what_is_correct=self.rule.what_is_correct,
                        severity=self.rule.severity,
                        file_path=filename,
                        normalized_content=re.sub(r"\s+", " ", line).strip(),
                        engine="ast",
                        start_column=start_col,
                        end_column=end_col,
                        symbol=target,
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
