import re

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
VALID_CHECK_TYPES = {"regex", "ast"}


def normalize_severity(severity: str | None) -> str:
    """Normalize rule severity to standard levels (CRITICAL, HIGH, MEDIUM, LOW, INFO)."""
    if not severity:
        return "HIGH"

    sev = severity.strip().upper()
    if sev in VALID_SEVERITIES:
        return sev

    # Backward compatibility mappings
    if sev == "ERROR":
        return "HIGH"
    elif sev in ("WARNING", "WARN"):
        return "MEDIUM"
    elif sev in ("NOTE", "NOTICE"):
        return "INFO"

    return "HIGH"


def validate_rule(rule_dict: dict) -> list[str]:
    """Validate a rule dictionary schema. Returns a list of error messages (empty if valid)."""
    errors = []

    # Required fields
    required_fields = {
        "rule_code": str,
        "title": str,
        "check_type": str,
        "check_language": str,
        "what_is_wrong": str,
        "what_is_correct": str,
    }

    for field, field_type in required_fields.items():
        if field not in rule_dict:
            errors.append(f"Missing required field: '{field}'")
        elif not isinstance(rule_dict[field], field_type):
            errors.append(
                f"Field '{field}' must be of type {field_type.__name__}, "
                f"got {type(rule_dict[field]).__name__}"
            )

    # Validate check_type value
    check_type = rule_dict.get("check_type")
    if check_type and check_type not in VALID_CHECK_TYPES:
        errors.append(
            f"Invalid 'check_type': '{check_type}'. Must be one of {list(VALID_CHECK_TYPES)}"
        )

    # Validate check_pattern for regex check_type
    if check_type == "regex":
        pattern = rule_dict.get("check_pattern")
        if not pattern:
            errors.append("Regex rules must specify a 'check_pattern'")
        elif not isinstance(pattern, str):
            errors.append("Field 'check_pattern' must be a string for regex checks")
        else:
            try:
                re.compile(pattern)
            except re.error as e:
                errors.append(f"Invalid regex check_pattern '{pattern}': {e}")

    # Validate confidence if present
    confidence = rule_dict.get("confidence")
    if confidence is not None:
        try:
            val = float(confidence)
            if not (0.0 <= val <= 1.0):
                errors.append("Field 'confidence' must be between 0.0 and 1.0")
        except (ValueError, TypeError):
            errors.append("Field 'confidence' must be a numeric value")

    return errors
