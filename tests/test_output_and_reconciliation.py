import csv
import shutil

import pytest
from lxml import etree

from edcimport.audit import verify
from edcimport.odm import XP_NS, validate_xsd
from edcimport.pipeline import ODM_XSD, ROOT, load_staging, run

from .conftest import RUN_DATE, SPEC

GOLDEN = ROOT / "tests/golden/discrepancy_baseline.csv"


@pytest.mark.req("REQ-OUT-01")
def test_odm_valid_against_xsd(demo_run):
    assert demo_run.xsd_errors == []


@pytest.mark.req("REQ-OUT-01")
def test_xsd_catches_undefined_item_oid(demo_run):
    tree = etree.parse(str(demo_run.out_dir / "odm_clinicaldata.xml"))
    tree.xpath("//odm:ItemData", namespaces=XP_NS)[0].set("ItemOID", "I.NOT.DEFINED")
    errors = validate_xsd(tree, str(ODM_XSD))
    assert errors and any("itemDataRef" in e or "I.NOT.DEFINED" in e for e in errors)


@pytest.mark.req("REQ-OUT-01")
def test_odm_values_are_transformed_values(demo_run):
    tree = etree.parse(str(demo_run.out_dir / "odm_clinicaldata.xml"))
    # S01-002 DM birth date arrived as 03/22/1971 -> ISO; 179 lb arrived for S01-001 Week 4 -> kg
    bd = tree.xpath("//odm:SubjectData[@SubjectKey='S01-002']//odm:ItemData[@ItemOID='I.DM.BRTHDTC']/@Value",
                    namespaces=XP_NS)
    wt = tree.xpath("//odm:SubjectData[@SubjectKey='S01-001']/odm:StudyEventData[@StudyEventOID='SE.WK4']"
                    "//odm:ItemData[@ItemOID='I.VS.WEIGHT']/@Value", namespaces=XP_NS)
    assert bd == ["1971-03-22"] and wt == ["81.2"]


@pytest.mark.req("REQ-OUT-02")
def test_discrepancy_report_columns(demo_run):
    with open(demo_run.out_dir / "discrepancies.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and set(rows[0]) == {"dataset", "record_no", "subject", "key", "item",
                                     "rule_id", "severity", "value", "message"}


@pytest.mark.req("REQ-REC-01")
def test_reconciliation_passes(demo_run):
    assert all(r.status == "PASS" for r in demo_run.recon)
    for r in demo_run.recon:
        assert r.source_records == r.accepted + r.rejected and r.odm_xpath_count == r.accepted


@pytest.mark.req("REQ-REC-02")
def test_xslt_roundtrip_and_sql_checks(demo_run, tmp_path):
    assert not any(r.dataset == "ITEMDATA_ROUNDTRIP" for r in demo_run.recon)
    assert load_staging(demo_run.out_dir, tmp_path / "staging.db") == []


@pytest.mark.req("REQ-REC-02")
def test_sql_checks_detect_tampered_staging(demo_run, tmp_path):
    run_copy = tmp_path / "run"
    shutil.copytree(demo_run.out_dir, run_copy)
    flat = run_copy / "odm_long.csv"
    lines = flat.read_text().splitlines()
    flat.write_text("\n".join(l for l in lines if ",IG.DM," not in l or "S01-001" not in l) + "\n")
    fails = load_staging(run_copy, tmp_path / "staging.db")
    assert {f[0] for f in fails} >= {"R1_record_count", "R2_orphan_subject"}


@pytest.mark.req("REQ-AUD-01")
def test_audit_chain_intact(demo_run):
    ok, msg = verify(demo_run.out_dir / "audit_trail.jsonl")
    assert ok, msg


@pytest.mark.req("REQ-AUD-01")
@pytest.mark.parametrize("tamper", ["edit", "delete", "swap"])
def test_audit_tampering_detected(demo_run, tmp_path, tamper):
    lines = (demo_run.out_dir / "audit_trail.jsonl").read_text().splitlines()
    if tamper == "edit":
        original = lines[3]                          # DM "VALIDATED" entry
        lines[3] = original.replace('"accepted": 7', '"accepted": 8')
        assert lines[3] != original
    elif tamper == "delete":
        del lines[2]
    else:
        lines[2], lines[3] = lines[3], lines[2]
    p = tmp_path / "audit.jsonl"
    p.write_text("\n".join(lines) + "\n")
    ok, _ = verify(p)
    assert not ok


@pytest.mark.req("REQ-AUD-02")
def test_run_refuses_to_overwrite_previous_evidence(demo_run):
    with pytest.raises(FileExistsError):
        run(SPEC, demo_run.out_dir.parent, run_date=RUN_DATE, run_id=demo_run.run_id)


@pytest.mark.req("REQ-REG-01")
def test_discrepancies_match_golden_baseline(demo_run):
    """Regression: any change in which records are flagged, and why, must be reviewed
    and the baseline re-approved deliberately (see docs/CHANGE_CONTROL.md)."""
    def key(r):
        return (r["dataset"], str(r["record_no"]), r["item"], r["rule_id"], r["severity"])
    with open(demo_run.out_dir / "discrepancies.csv") as fh:
        actual = sorted(key(r) for r in csv.DictReader(fh))
    with open(GOLDEN) as fh:
        expected = sorted(key(r) for r in csv.DictReader(fh))
    assert actual == expected
