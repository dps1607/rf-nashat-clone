"""
Form helpers — render AgentConfig as editable form structure, parse it back.

The strategy:
- For rendering, we walk the YAML dict (loaded by ruamel.yaml in round-trip
  mode, so comments/quoting/inline-lists are preserved) and emit a sequence
  of "field descriptors" the Jinja template can iterate over.
- For parsing, we accept the form POST data, reconstruct the YAML dict, and
  validate it against the Pydantic schema before writing to disk.

Why ruamel.yaml (not PyYAML): PyYAML's yaml.safe_dump destroys comments,
rewrites quoted strings, flattens inline lists, and can embed \\r\\n as literal
escape sequences — every save would destructively normalize the file.
ruamel.yaml's round-trip mode preserves all of that exactly.
"""
from __future__ import annotations
import io
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config.schema import AgentConfig, validate_default_mode_exists

# Shared round-trip YAML instance. Configured once so every load/save
# uses identical formatting rules.
#
# Width is set to a very large number so ruamel never hard-wraps long strings
# mid-value — this preserves one-line quoted strings that the original files
# use extensively. Indent settings match the 2/4/2 convention already in use
# across the project YAMLs.
_yaml = YAML(typ="rt")
_yaml.preserve_quotes = True
_yaml.width = 4096
_yaml.indent(mapping=2, sequence=4, offset=2)


def load_yaml(path: Path) -> CommentedMap:
    """Load YAML preserving comments, quoting, and structure."""
    with open(path) as f:
        data = _yaml.load(f)
    return data if data is not None else CommentedMap()


def save_yaml(path: Path, data: Any) -> None:
    """Write YAML back to disk in round-trip mode.

    Preserves comments, quote styles, inline flow collections, and blank
    lines that were present when the file was originally loaded.
    """
    with open(path, "w") as f:
        _yaml.dump(data, f)


def validate(data: Any) -> tuple[bool, str]:
    """Run the dict through Pydantic. Return (ok, error_message).

    ruamel's CommentedMap/CommentedSeq inherit from dict/list so Pydantic
    accepts them directly. No conversion needed.
    """
    try:
        config = AgentConfig(**data)
        validate_default_mode_exists(config)
        return True, ""
    except Exception as e:
        return False, str(e)


# -----------------------------------------------------------------------------
# RENDER — convert form POST data into a YAML-shaped dict
# -----------------------------------------------------------------------------
#
# The form uses bracket notation in field names so we can reconstruct nesting:
#   persona[name]
#   persona[handle]
#   behavior[purpose]
#   behavior[temperature]
#   behavior[custom_instructions][0]
#   behavior[custom_instructions][1]
#   behavior[modes][public_default][label]
#   guardrails[never_do][0]
#
# parse_form_data() walks the flat POST dict and rebuilds the nested structure.

def parse_form_data(form: dict, original: dict) -> dict:
    """Merge form data on top of the original YAML structure.

    `original` is the YAML as it currently lives on disk. We start from it
    so any fields not represented in the form (e.g., audience tiers if we
    don't render them) are preserved. Form data overrides only what was edited.
    """
    result = _deep_copy(original)


    for raw_key, raw_value in form.items():
        # Skip empty list slots — the form sends one extra blank for "add new"
        if raw_value == "" and "[" in raw_key and raw_key.endswith("]"):
            # Allow empty values for explicit string fields, just not for list rows
            tail = raw_key.rsplit("[", 1)[-1].rstrip("]")
            if tail.isdigit():
                continue

        path = _parse_key(raw_key)
        if not path:
            continue
        value = _coerce_value(raw_key, raw_value)
        _set_nested(result, path, value)

    # After merge: rebuild list-typed fields cleanly so removed items don't linger
    _rebuild_lists_from_form(result, form)
    return result


def _parse_key(key: str) -> list:
    """Parse 'a[b][c][0]' into ['a', 'b', 'c', 0]."""
    if "[" not in key:
        return [key]
    head, _, rest = key.partition("[")
    parts = [head]
    for token in rest.replace("]", "").split("["):
        if token.isdigit():
            parts.append(int(token))
        elif token:
            parts.append(token)
    return parts


# Fields that are numeric — coerce on parse so YAML stays typed correctly
_NUMERIC_FLOAT_FIELDS = {"temperature", "similarity_threshold"}
_NUMERIC_INT_FIELDS = {
    "max_tokens", "top_k", "coaching_n", "reference_n", "published_n",
    "message_limit", "voice_minute_limit", "response_length_custom_value",
}
_BOOLEAN_FIELDS = {
    "disclaimer_enabled", "show_citations", "reranker_enabled", "resets_monthly",
}


def _coerce_value(key: str, value: Any) -> Any:
    """Convert form strings to typed Python values based on the field name."""
    if value is None:
        return None
    leaf = key.rsplit("[", 1)[-1].rstrip("]")
    if leaf in _BOOLEAN_FIELDS:
        return str(value).lower() in ("true", "1", "yes", "on")
    if leaf in _NUMERIC_INT_FIELDS:
        if value == "" or value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if leaf in _NUMERIC_FLOAT_FIELDS:
        if value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def _set_nested(obj: Any, path: list, value: Any) -> None:
    """Set obj[path[0]][path[1]]... = value, creating intermediate dicts as needed."""
    cur = obj
    for i, key in enumerate(path[:-1]):
        nxt = path[i + 1]
        if isinstance(key, int):
            while len(cur) <= key:
                cur.append({} if not isinstance(nxt, int) else [])
            if cur[key] is None:
                cur[key] = {} if not isinstance(nxt, int) else []
            cur = cur[key]
        else:
            if key not in cur or cur[key] is None:
                cur[key] = {} if not isinstance(nxt, int) else []
            cur = cur[key]
    last = path[-1]
    if isinstance(last, int):
        while len(cur) <= last:
            cur.append("")
        cur[last] = value
    else:
        cur[last] = value


def _deep_copy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj


# List-of-strings fields and where they live in the YAML structure.
# After form merge, we rebuild these from the form data so deletions stick.
_LIST_FIELDS = [
    ["persona", "pinned_questions"],
    ["behavior", "custom_instructions"],
    ["guardrails", "never_do"],
    ["guardrails", "always_do"],
    ["guardrails", "character_rules"],
    ["guardrails", "domain_knowledge_rules"],
    ["guardrails", "escalation_rules"],
    ["guardrails", "sales_directives"],
    ["knowledge", "knowledge_collections"],
    ["knowledge", "staff_exclusions"],
]


def _rebuild_lists_from_form(result: dict, form: dict) -> None:
    """For each known list field, collect indexed entries from the form
    in order, drop blanks, and replace the list in result."""
    for path in _LIST_FIELDS:
        prefix = "".join(path[:1] + [f"[{p}]" for p in path[1:]]) + "["
        items: list[tuple[int, str]] = []
        for k, v in form.items():
            if k.startswith(prefix) and k.endswith("]"):
                idx_str = k[len(prefix):-1]
                if idx_str.isdigit() and isinstance(v, str) and v.strip():
                    items.append((int(idx_str), v.strip()))
        items.sort(key=lambda x: x[0])
        new_list = [v for _, v in items]
        # Walk to the parent and replace
        parent = result
        for p in path[:-1]:
            parent = parent.setdefault(p, {})
        parent[path[-1]] = new_list
