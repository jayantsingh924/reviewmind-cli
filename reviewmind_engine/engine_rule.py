"""
EngineRule — a plain dataclass representation of a Rule for the engine.

Why this exists:
  The private backend uses SQLAlchemy ORM Rule models.
  The public engine must NOT depend on SQLAlchemy.

  Anywhere the engine is called (CLI or backend), convert the
  rule object to EngineRule first.

Usage in private backend:
    from reviewmind_engine.engine_rule import EngineRule
    engine_rules = [EngineRule.from_orm(r) for r in active_rules]
    findings = engine.run_scan(files, rules=engine_rules)

Usage in CLI:
    Rules are fetched as JSON from the API and deserialized directly
    into EngineRule using EngineRule.from_dict(rule_json).
"""

from dataclasses import dataclass


@dataclass
class EngineRule:
    rule_code: str
    title: str
    check_type: str  # "regex" | "ast"
    check_pattern: str | None
    check_language: str  # "python" | "javascript" | "typescript" | "any"
    severity: str  # "error" | "warning" | "info"
    what_is_wrong: str
    what_is_correct: str
    supports_autofix: bool = False
    supports_ast: bool = False
    requires_language: str | None = None
    confidence: float = 0.9

    @classmethod
    def from_orm(cls, rule) -> "EngineRule":
        """Convert a SQLAlchemy Rule ORM object to EngineRule."""
        return cls(
            rule_code=rule.rule_code,
            title=rule.title,
            check_type=rule.check_type,
            check_pattern=rule.check_pattern,
            check_language=rule.check_language,
            severity=rule.severity,
            what_is_wrong=rule.what_is_wrong,
            what_is_correct=rule.what_is_correct,
            supports_autofix=rule.supports_autofix,
            supports_ast=rule.supports_ast,
            requires_language=rule.requires_language,
            confidence=rule.confidence,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EngineRule":
        """Deserialize from API JSON response (used by CLI)."""
        return cls(
            rule_code=data["rule_code"],
            title=data["title"],
            check_type=data["check_type"],
            check_pattern=data.get("check_pattern"),
            check_language=data["check_language"],
            severity=data.get("severity", "error"),
            what_is_wrong=data.get("what_is_wrong", ""),
            what_is_correct=data.get("what_is_correct", ""),
            supports_autofix=data.get("supports_autofix", False),
            supports_ast=data.get("supports_ast", False),
            requires_language=data.get("requires_language"),
            confidence=data.get("confidence", 0.9),
        )
