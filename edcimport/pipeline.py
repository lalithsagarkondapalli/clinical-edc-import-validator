"""Orchestrates one import run: read -> validate/transform -> ODM -> XSD -> reconcile -> evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from lxml import etree

from . import __version__
from .audit import AuditTrail
from .odm import build_odm, count_records, validate_xsd
from .readers import FileIssue, read_source
from .validate import DatasetValidator, Discrepancy

ROOT = Path(__file__).resolve().parents[1]
ODM_XSD = ROOT / "schemas/odm1-3-2_import_subset.xsd"
FLATTEN_XSL = ROOT / "xslt/odm_to_long_csv.xsl"
DATASET_ORDER = ["DM", "VS", "LB", "AE"]   # DM first: it defines registered subjects


@dataclass
class ReconRow:
    dataset: str
    source_records: int
    accepted: int
    rejected: int
    odm_xpath_count: int
    status: str


@dataclass
class RunResult:
    run_id: str
    out_dir: Path
    recon: list[ReconRow]
    discrepancies: list[Discrepancy]
    xsd_errors: list[str]
    flat_rows: int

    @property
    def ok(self) -> bool:
        return not self.xsd_errors and all(r.status == "PASS" for r in self.recon)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "uncommitted"


def load_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run(spec_path: Path, out_root: Path, base_dir: Path = ROOT,
        run_date: date | None = None, run_id: str | None = None) -> RunResult:
    spec = load_spec(spec_path)
    now = datetime.now(timezone.utc)
    run_date = run_date or now.date()
    run_id = run_id or f"{spec['study']['oid']}_{now:%Y%m%dT%H%M%SZ}"
    out = out_root / run_id
    out.mkdir(parents=True, exist_ok=False)          # never overwrite a prior run's evidence

    audit = AuditTrail(out / "audit_trail.jsonl", run_id)
    audit.log("RUN_START", spec=str(spec_path.name), spec_version=spec["study"]["spec_version"],
              tool_version=__version__, git_commit=_git_commit(), run_date=run_date.isoformat())

    accepted_by_ds, all_disc, recon_counts, inputs = {}, [], {}, []
    registered: set[str] | None = None

    for name in DATASET_ORDER:
        ds = spec["datasets"][name]
        rr = read_source(ds["source"], base_dir)
        inputs.append({"dataset": name, "file": ds["source"]["path"], "sha256": rr.sha256, "bytes": rr.bytes})
        audit.log("INPUT_RECEIVED", dataset=name, file=ds["source"]["path"], sha256=rr.sha256,
                  records=len(rr.records))

        # JSON header checks against the spec's expected header values
        if ds.get("expected_header"):
            hdr = json.loads((base_dir / ds["source"]["path"]).read_text()).get("header", {})
            for k, v in ds["expected_header"].items():
                if hdr.get(k) != v:
                    rr.issues.append(FileIssue("F-HDR", f"header {k}={hdr.get(k)!r}, expected {v!r}"))

        file_errors = [i for i in rr.issues if i.severity == "error"]
        if file_errors:
            # Quarantine: a structurally bad transfer is never partially loaded.
            for i in rr.issues:
                all_disc.append(Discrepancy(name, "FILE", None, "", "", i.rule_id, i.severity, None, i.message))
            audit.log("FILE_QUARANTINED", dataset=name, reasons=[i.message for i in file_errors])
            accepted, disc = [], []
        else:
            v = DatasetValidator(name, ds, spec, run_date, registered)
            accepted, disc = v.run(rr.records)
            audit.log("TRANSFORMED", dataset=name, **asdict(v.stats))

        all_disc.extend(disc)
        accepted_by_ds[name] = accepted
        n_rej = len(rr.records) - len(accepted)
        recon_counts[name] = (len(rr.records), len(accepted), n_rej)
        audit.log("VALIDATED", dataset=name, accepted=len(accepted), rejected=n_rej,
                  errors=sum(d.severity == "error" for d in disc))
        if name == "DM":
            registered = {r.subject for r in accepted}

    # ---- ODM build + schema validation
    tree = build_odm(spec, accepted_by_ds, file_oid=run_id, created=now)
    odm_path = out / "odm_clinicaldata.xml"
    tree.write(str(odm_path), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    xsd_errors = validate_xsd(tree, str(ODM_XSD))
    audit.log("ODM_WRITTEN", file=odm_path.name, sha256=hashlib.sha256(odm_path.read_bytes()).hexdigest())
    audit.log("XSD_VALIDATION", schema=ODM_XSD.name, valid=not xsd_errors, errors=xsd_errors[:20])

    # ---- XSLT round-trip flatten (independent of the builder)
    flat = str(etree.XSLT(etree.parse(str(FLATTEN_XSL)))(etree.parse(str(odm_path))))
    flat_path = out / "odm_long.csv"
    flat_path.write_text(flat, encoding="utf-8")
    flat_rows = len(flat.strip().splitlines()) - 1
    expected_items = sum(len(r.items) for recs in accepted_by_ds.values() for r in recs)

    # ---- reconciliation
    recon = []
    for name in DATASET_ORDER:
        src, acc, rej = recon_counts[name]
        xp = count_records(tree, spec["datasets"][name]["item_group_oid"])
        status = "PASS" if (src == acc + rej and xp == acc) else "FAIL"
        recon.append(ReconRow(name, src, acc, rej, xp, status))
    if flat_rows != expected_items:
        recon.append(ReconRow("ITEMDATA_ROUNDTRIP", expected_items, flat_rows, 0, flat_rows, "FAIL"))
    audit.log("RECONCILIATION", results=[asdict(r) for r in recon],
              itemdata_expected=expected_items, itemdata_flattened=flat_rows)

    # ---- evidence files
    _write_csv(out / "discrepancies.csv", [asdict(d) for d in all_disc], list(Discrepancy.__dataclass_fields__))
    _write_csv(out / "reconciliation.csv", [asdict(r) for r in recon], list(ReconRow.__dataclass_fields__))
    manifest = {"run_id": run_id, "tool_version": __version__, "git_commit": _git_commit(),
                "spec": spec_path.name, "spec_version": spec["study"]["spec_version"],
                "run_date": run_date.isoformat(), "created_utc": now.isoformat(),
                "inputs": inputs, "odm_sha256": hashlib.sha256(odm_path.read_bytes()).hexdigest(),
                "xsd_valid": not xsd_errors,
                "result": "PASS" if (not xsd_errors and all(r.status == "PASS" for r in recon)) else "FAIL"}
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    audit.log("RUN_END", result=manifest["result"], discrepancies=len(all_disc))
    return RunResult(run_id, out, recon, all_disc, xsd_errors, flat_rows)


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load_staging(run_dir: Path, db_path: Path) -> list[tuple]:
    """Load a run's flattened ODM + evidence into SQLite and run the SQL reconciliation checks.
    Returns failing rows (empty list == all checks passed)."""
    con = sqlite3.connect(db_path)
    con.executescript((ROOT / "sql/sqlite/01_staging_ddl.sql").read_text())
    for table, fname in [("stg_item_data", "odm_long.csv"), ("stg_discrepancy", "discrepancies.csv"),
                         ("stg_reconciliation", "reconciliation.csv")]:
        with open(run_dir / fname, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))[1:]
        if rows:
            con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)
    con.commit()
    failures = []
    for stmt in (ROOT / "sql/sqlite/02_reconciliation_checks.sql").read_text().split(";"):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            failures.extend(con.execute(body).fetchall())
    con.close()
    return failures
