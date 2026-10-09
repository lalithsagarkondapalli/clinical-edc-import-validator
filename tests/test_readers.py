import json

import pytest

from edcimport.pipeline import ROOT, load_spec, run
from edcimport.readers import read_source

from .conftest import RUN_DATE, SPEC

spec = load_spec(SPEC)


@pytest.mark.req("REQ-IN-01")
@pytest.mark.parametrize("ds,expected", [("DM", 11), ("VS", 16), ("LB", 7), ("AE", 5)])
def test_each_format_reads_expected_record_count(ds, expected):
    rr = read_source(spec["datasets"][ds]["source"], ROOT)
    assert len(rr.records) == expected
    assert all(v is None or isinstance(v, str) for r in rr.records for v in r.values.values())


@pytest.mark.req("REQ-IN-01")
def test_xml_namespaced_xpath_extracts_attributes_and_text():
    rr = read_source(spec["datasets"]["AE"]["source"], ROOT)
    first = rr.records[0].values
    assert first["SUBJID"] == "S01-001" and first["AESEQ"] == "1" and first["AETERM"] == "Headache"
    assert rr.records[1].values["AEENDTC"] is None          # optional element absent


@pytest.mark.req("REQ-IN-02")
def test_input_checksums_recorded(demo_run):
    manifest = json.loads((demo_run.out_dir / "run_manifest.json").read_text())
    assert len(manifest["inputs"]) == 4
    assert all(len(i["sha256"]) == 64 for i in manifest["inputs"])
    audit = (demo_run.out_dir / "audit_trail.jsonl").read_text()
    for i in manifest["inputs"]:
        assert i["sha256"] in audit


@pytest.mark.req("REQ-IN-03")
def test_xml_failing_vendor_xsd_is_quarantined(workspace):
    f = workspace / "data/source/CARD301_AE_safetyvendor.xml"
    f.write_text(f.read_text().replace("<sv:Term>Headache</sv:Term>", "", 1))   # required element removed
    res = run(workspace / "specs/CARD301_transfer_spec.yaml", workspace / "out",
              base_dir=workspace, run_date=RUN_DATE, run_id="R")
    ae = next(r for r in res.recon if r.dataset == "AE")
    assert ae.accepted == 0 and ae.rejected == 5 and ae.status == "PASS"
    assert any(d.rule_id == "F-XSD" and d.dataset == "AE" for d in res.discrepancies)


@pytest.mark.req("REQ-IN-04")
@pytest.mark.parametrize("field,value,rule", [("record_count", 99, "F-COUNT"),
                                              ("vendor", "OTHER-LAB", "F-HDR")])
def test_json_header_mismatch_is_quarantined(workspace, field, value, rule):
    f = workspace / "data/source/CARD301_LB_centrallab.json"
    doc = json.loads(f.read_text())
    doc["header"][field] = value
    f.write_text(json.dumps(doc))
    res = run(workspace / "specs/CARD301_transfer_spec.yaml", workspace / "out",
              base_dir=workspace, run_date=RUN_DATE, run_id="R")
    lb = next(r for r in res.recon if r.dataset == "LB")
    assert lb.accepted == 0
    assert any(d.rule_id == rule for d in res.discrepancies)
