import re
from reviewmind_engine.evaluators.base import RuleEvaluator
from reviewmind_engine.finding import Finding

class RegexRuleEvaluator(RuleEvaluator):
    def __init__(self, rule):
        super().__init__(rule)
        self.pattern = None
        if rule.check_pattern:
            try:
                self.pattern = re.compile(rule.check_pattern, re.IGNORECASE)
            except Exception:
                pass

    def evaluate_file(self, filename: str, content: str, added_lines: set[int], context: dict | None = None) -> list[Finding]:
        if not self.pattern:
            return []
        findings = []
        lines = content.splitlines()
        for i, line in enumerate(lines, start=1):
            if i not in added_lines:
                continue
            if self.pattern.search(line):
                findings.append(Finding(
                    rule_code=self.rule.rule_code,
                    title=self.rule.title,
                    message=f"Rule Violation: {self.rule.rule_code} - {self.rule.title}\n{self.rule.what_is_wrong}\nCorrect way: {self.rule.what_is_correct}",
                    line=i,
                    what_is_wrong=self.rule.what_is_wrong,
                    what_is_correct=self.rule.what_is_correct,
                    severity=self.rule.severity,
                    file_path=filename,
                    normalized_content=re.sub(r"\s+", " ", line).strip(),
                    engine="regex",
                    symbol=self.rule.check_pattern,
                    category="style",
                    remediation=self.rule.what_is_correct,
                    confidence=self.rule.confidence
                ))
        return findings
