"""Case-type template registry — T53-M2.

Loads and validates chargesheet mindmap templates at startup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

from app.mindmap.schemas import TemplateSummary, TemplateTree

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_registry: Dict[str, TemplateTree] = {}
_loaded = False

# Fallback generic template for unknown or uncertain case categories
_GENERIC_TEMPLATE = TemplateTree(
    case_category="generic",
    template_version="1.0.0",
    description="Generic chargesheet mindmap template for unclassified cases",
    branches=[],
)


def _load_all() -> None:
    """Load and validate every JSON template in the templates/ directory."""
    global _loaded
    if _loaded:
        return

    if not _TEMPLATES_DIR.is_dir():
        raise RuntimeError(
            f"Template directory not found: {_TEMPLATES_DIR}. "
            "Server cannot start without chargesheet mindmap templates."
        )

    json_files = sorted(_TEMPLATES_DIR.glob("*.json"))
    if not json_files:
        raise RuntimeError(
            f"No template JSON files found in {_TEMPLATES_DIR}. "
            "At least one template is required."
        )

    for fp in json_files:
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            tree = TemplateTree.model_validate(raw)
            _registry[tree.case_category] = tree
            logger.info(
                "Loaded mindmap template: %s (v%s, %d branches)",
                tree.case_category,
                tree.template_version,
                len(tree.branches),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Invalid mindmap template {fp.name}: {exc}"
            ) from exc

    _loaded = True
    logger.info("Template registry loaded: %d templates", len(_registry))


def load_template(case_category: str) -> TemplateTree:
    """Return the template tree for a given case category.

    Falls back to the generic template if no match is found.
    """
    _load_all()
    return _registry.get(case_category, _GENERIC_TEMPLATE)


def list_templates() -> list[TemplateSummary]:
    """Return summary info for every registered template."""
    _load_all()
    result = []
    for tree in _registry.values():
        total = sum(1 + len(b.children) for b in tree.branches)
        result.append(
            TemplateSummary(
                case_category=tree.case_category,
                template_version=tree.template_version,
                description=tree.description,
                branch_count=len(tree.branches),
                total_nodes=total,
            )
        )
    return result


def template_version(case_category: str) -> str:
    """Return the template version string for audit purposes."""
    _load_all()
    tmpl = _registry.get(case_category)
    if tmpl:
        return tmpl.template_version
    return _GENERIC_TEMPLATE.template_version


def reload_templates() -> None:
    """Force a fresh reload (useful for tests)."""
    global _loaded
    _registry.clear()
    _loaded = False
    _load_all()
