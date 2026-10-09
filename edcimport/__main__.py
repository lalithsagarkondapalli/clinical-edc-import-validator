"""Command line entry point.

    python -m edcimport run          --spec specs/CARD301_transfer_spec.yaml --out out
    python -m edcimport verify-audit out/<run_id>/audit_trail.jsonl
    python -m edcimport load-staging out/<run_id>

Exit codes: 0 = run reconciled and ODM is schema-valid (record-level discrepancies are
expected and reported, not fatal); 2 = reconciliation/XSD failure or broken audit chain;
3 = --fail-on-error was set and error discrepancies exist.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from .audit import verify
from .pipeline import load_staging, run


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="edcimport")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="import, validate and export one transfer")
    r.add_argument("--spec", type=Path, required=True)
    r.add_argument("--out", type=Path, default=Path("out"))
    r.add_argument("--run-date", type=date.fromisoformat, help="as-of date for future-date checks")
    r.add_argument("--run-id")
    r.add_argument("--fail-on-error", action="store_true")
    v = sub.add_parser("verify-audit", help="check the audit trail hash chain")
    v.add_argument("path", type=Path)
    s = sub.add_parser("load-staging", help="load a run into SQLite and run SQL reconciliation")
    s.add_argument("run_dir", type=Path)
    a = p.parse_args(argv)

    if a.cmd == "run":
        res = run(a.spec, a.out, run_date=a.run_date, run_id=a.run_id)
        print(f"Run {res.run_id} -> {res.out_dir}")
        print(f"{'dataset':<20}{'source':>8}{'accepted':>10}{'rejected':>10}{'in ODM':>8}  status")
        for x in res.recon:
            print(f"{x.dataset:<20}{x.source_records:>8}{x.accepted:>10}{x.rejected:>10}"
                  f"{x.odm_xpath_count:>8}  {x.status}")
        print(f"ODM schema valid: {not res.xsd_errors}")
        by_rule = Counter((d.dataset, d.rule_id) for d in res.discrepancies)
        print("Discrepancies by rule: " + ", ".join(f"{d}/{r}={n}" for (d, r), n in sorted(by_rule.items())))
        if not res.ok:
            for e in res.xsd_errors:
                print("  XSD:", e, file=sys.stderr)
            return 2
        if a.fail_on_error and any(d.severity == "error" for d in res.discrepancies):
            return 3
        return 0
    if a.cmd == "verify-audit":
        ok, msg = verify(a.path)
        print(msg)
        return 0 if ok else 2
    if a.cmd == "load-staging":
        fails = load_staging(a.run_dir, a.run_dir / "staging.db")
        for f in fails:
            print("FAIL", f)
        print("SQL reconciliation: " + ("PASS" if not fails else f"{len(fails)} failing rows"))
        return 0 if not fails else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
