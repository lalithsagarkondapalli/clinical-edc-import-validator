"""Static check: every requirement is referenced by at least one test, and no test cites an unknown ID."""
import ast
from pathlib import Path

import pytest


def _req_ids_in_tests() -> set[str]:
    ids = set()
    for f in Path(__file__).parent.glob("test_*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            if (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "req"):
                ids.update(a.value for a in node.args if isinstance(a, ast.Constant))
    return ids


def test_every_requirement_has_a_test(requirements):
    missing = set(requirements) - _req_ids_in_tests()
    assert not missing, f"requirements without tests: {sorted(missing)}"


def test_no_test_cites_unknown_requirement(requirements):
    unknown = _req_ids_in_tests() - set(requirements)
    assert not unknown, f"tests reference undefined requirement IDs: {sorted(unknown)}"
