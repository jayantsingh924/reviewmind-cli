import ast
import logging
from reviewmind_engine.finding import Finding
from reviewmind_engine.evaluators import get_evaluator

logger = logging.getLogger(__name__)


class AnalysisEngine:
    def __init__(self, rules=None):
        self.rules = rules or []

    def run_scan(self, files_or_rules, files=None, file_added_lines=None) -> list[Finding]:
        # Case A: Instance call -> engine.run_scan(files)
        # self is an AnalysisEngine instance.
        if isinstance(self, AnalysisEngine):
            rules = self.rules
            actual_files = files_or_rules
            processed_files = []
            for f in actual_files:
                processed_files.append({
                    "filename": f["filename"],
                    "content": f["content"],
                    "added_lines": f.get("added_lines", set())
                })
            return self._scan_internal(rules, processed_files)
            
        # Case B: Static call -> AnalysisEngine.run_scan(active_rules, files, file_added_lines)
        # self is actually the list of rules.
        else:
            rules = self
            actual_files = files_or_rules
            added_lines_map = files or {}
            processed_files = []
            for f in actual_files:
                fname = f["filename"]
                processed_files.append({
                    "filename": fname,
                    "content": f["content"],
                    "added_lines": added_lines_map.get(fname, set())
                })
            return AnalysisEngine._scan_internal(rules, processed_files)

    @staticmethod
    def _scan_internal(rules: list, files: list[dict]) -> list[Finding]:
        all_findings = []
        evaluators = [get_evaluator(r) for r in rules]

        for file in files:
            filename = file["filename"]
            file_content = file["content"]
            
            added_lines = file.get("added_lines", set())
            if not added_lines:
                continue

            file_evaluators = []
            for ev in evaluators:
                r = ev.rule
                
                # Check target language constraints dynamically
                lang = getattr(r, "requires_language", None) or getattr(r, "check_language", None)
                if isinstance(lang, str):
                    lang = lang.lower()
                elif hasattr(lang, "value"): # Handle Enum
                    lang = lang.value.lower()
                    
                if lang == "python" and not filename.endswith(".py"):
                    continue
                if lang in ("javascript", "typescript") and not filename.endswith((".js", ".ts", ".jsx", ".tsx")):
                    continue
                
                file_evaluators.append(ev)
            
            if not file_evaluators:
                continue

            # Pre-parse AST once per file (shared context)
            context = {}
            if filename.endswith(".py"):
                try:
                    context["ast"] = ast.parse(file_content)
                except Exception:
                    context["ast"] = None

            # Run evaluators at file level
            for ev in file_evaluators:
                rule = ev.rule
                try:
                    findings = ev.evaluate_file(filename, file_content, added_lines, context=context)
                    all_findings.extend(findings)
                except Exception as exc:
                    logger.warning("Evaluator failed for rule %s on %s: %s", getattr(rule, "rule_code", "unknown"), filename, exc)
                    continue

        return all_findings
