import hashlib
from dataclasses import dataclass


@dataclass
class Finding:
    rule_code: str
    title: str
    message: str
    line: int
    what_is_wrong: str
    what_is_correct: str
    severity: str
    file_path: str
    normalized_content: str
    suggestion: str | None = None

    # Advanced IR Fields
    engine: str = "regex"
    start_column: int | None = None
    end_column: int | None = None
    symbol: str | None = None
    category: str | None = None
    remediation: str | None = None
    confidence: float = 1.0

    @property
    def fingerprint(self) -> str:
        # Standard fingerprint based on rule_code, file path, and normalized content string
        raw_str = f"{self.rule_code}:{self.file_path}:{self.normalized_content}"
        return hashlib.sha256(raw_str.encode()).hexdigest()
