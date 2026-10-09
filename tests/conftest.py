"""Shared fixtures + traceability evidence.

Each test declares the requirement(s) it verifies with @pytest.mark.req("REQ-..").
At the end of the session a requirement -> test -> result matrix is written to
out/test_evidence/traceability_matrix.md (CI uploads it as a build artifact).
"""
from __future__ import annotations

import platform
import shutil
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml

from edcimport import __version__
from edcimport.pipeline import ROOT, run

SPEC = ROOT / "specs/CARD301_transfer_spec.yaml"
RUN_DATE = date(2026, 4, 15)
_results: dict[str, list[tuple[str, str]]] = defaultdict(list)


def pytest_configure(config):
    config.addinivalue_line("markers", "req(*ids): requirement IDs verified by this test")


@pytest.fixture(scope="session")
def requirements() -> dict:
    return yaml.safe_load((ROOT / "validation/requirements.yaml").read_text())


@pytest.fixture(scope="session")
def demo_run(tmp_path_factory):
    """One full pipeline run on the reference dataset, shared by read-only tests."""
    return run(SPEC, tmp_path_factory.mktemp("runs"), run_date=RUN_DATE, run_id="TEST_RUN")


@pytest.fixture
def workspace(tmp_path):
    """A disposable copy of spec + data, for tests that need to mutate inputs."""
    for d in ("specs", "data", "schemas"):
        shutil.copytree(ROOT / d, tmp_path / d)
    return tmp_path


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        for m in item.iter_markers("req"):
            for rid in m.args:
                _results[rid].append((item.nodeid, rep.outcome.upper()))


def pytest_sessionfinish(session, exitstatus):
    reqs = yaml.safe_load((ROOT / "validation/requirements.yaml").read_text())
    out = ROOT / "out/test_evidence"
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Traceability Matrix (generated)", "",
        f"- Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        f"- Tool version: {__version__} | Python {platform.python_version()}", "",
        "| Requirement | Description | Test | Result |", "|---|---|---|---|",
    ]
    for rid, desc in reqs.items():
        tests = _results.get(rid) or [("**NOT COVERED**", "FAIL")]
        for nodeid, res in tests:
            lines.append(f"| {rid} | {desc} | `{nodeid}` | {res} |")
    (out / "traceability_matrix.md").write_text("\n".join(lines) + "\n")
