"""Unit tests for individual rules, using small hand-built records (one rule per test)."""
import pytest

from edcimport.pipeline import load_spec
from edcimport.readers import SourceRecord
from edcimport.validate import DatasetValidator

from .conftest import RUN_DATE, SPEC

spec = load_spec(SPEC)
GOOD_VS = {"SUBJID": "S01-001", "VISIT": "Screening", "VS_DATE": "2026-03-02", "SYSBP": "130",
           "DIABP": "80", "PULSE": "70", "WEIGHT": "80", "WEIGHT_UNIT": "kg"}


def vs(registered=frozenset({"S01-001"}), **overrides):
    rec = SourceRecord(1, {**GOOD_VS, **overrides})
    v = DatasetValidator("VS", spec["datasets"]["VS"], spec, RUN_DATE, set(registered))
    acc, disc = v.run([rec])
    return acc, disc, v.stats


def rules(disc):
    return {d.rule_id for d in disc}


@pytest.mark.req("REQ-MAP-01")
def test_clean_record_maps_to_spec_item_oids():
    acc, disc, _ = vs()
    assert disc == []
    assert set(acc[0].items) == {i["oid"] for i in spec["datasets"]["VS"]["items"]}
    assert acc[0].event_oid == "SE.SCR" and acc[0].site == "S01"


@pytest.mark.req("REQ-MAP-02")
@pytest.mark.parametrize("raw", ["2026-03-02", "03/02/2026", "02-Mar-2026", "20260302"])
def test_dates_normalised_to_iso(raw):
    acc, disc, _ = vs(VS_DATE=raw)
    assert disc == [] and acc[0].items["I.VS.VSDTC"] == "2026-03-02"


@pytest.mark.req("REQ-MAP-03")
def test_codelist_decode():
    v = DatasetValidator("DM", spec["datasets"]["DM"], spec, RUN_DATE, None)
    acc, disc = v.run([SourceRecord(1, {"SUBJID": "S01-001", "SITE": "S01", "BIRTH_DATE": "1970-01-01",
                                        "SEX": "Female", "RACE": None})])
    assert disc == [] and acc[0].items["I.DM.SEX"] == "F" and v.stats.codes_decoded == 1


@pytest.mark.req("REQ-MAP-04")
def test_unit_converted_before_range_check():
    acc, disc, stats = vs(WEIGHT="179", WEIGHT_UNIT="lb")   # 179 lb = 81.2 kg, in range
    assert disc == [] and acc[0].items["I.VS.WEIGHT"] == "81.2" and stats.units_converted == 1
    _, disc, _ = vs(WEIGHT="600", WEIGHT_UNIT="lb")          # 272 kg -> out of range in kg
    assert rules(disc) == {"V-RANGE"}


@pytest.mark.req("REQ-VAL-01")
def test_required_missing():
    _, disc, _ = vs(SYSBP=None)
    assert rules(disc) == {"V-REQ"}


@pytest.mark.req("REQ-VAL-01")
def test_optional_missing_is_fine():
    acc, disc, _ = vs(PULSE=None)
    assert disc == [] and "I.VS.PULSE" not in acc[0].items


@pytest.mark.req("REQ-VAL-02")
@pytest.mark.parametrize("field,raw", [("PULSE", "abc"), ("SYSBP", "120.5"), ("WEIGHT", "80,5")])
def test_type_errors(field, raw):
    _, disc, _ = vs(**{field: raw})
    assert rules(disc) == {"V-TYPE"}


@pytest.mark.req("REQ-VAL-03")
@pytest.mark.parametrize("sysbp,ok", [("60", True), ("250", True), ("59", False), ("251", False)])
def test_range_boundaries_inclusive(sysbp, ok):
    _, disc, _ = vs(SYSBP=sysbp, DIABP="40")
    assert (disc == []) is ok


@pytest.mark.req("REQ-VAL-04")
@pytest.mark.parametrize("subj,registered,rule", [
    ("S9-1", {"S9-1"}, "V-SUBJ-PATTERN"),
    ("S04-001", {"S04-001"}, "V-SUBJ-PATTERN"),
    ("S01-002", {"S01-001"}, "V-SUBJ-REF"),
])
def test_subject_rules(subj, registered, rule):
    _, disc, _ = vs(registered=registered, SUBJID=subj)
    assert rule in rules(disc)


@pytest.mark.req("REQ-VAL-04")
def test_dm_site_must_match_subject_prefix():
    v = DatasetValidator("DM", spec["datasets"]["DM"], spec, RUN_DATE, None)
    _, disc = v.run([SourceRecord(1, {"SUBJID": "S01-001", "SITE": "S02", "BIRTH_DATE": "1970-01-01",
                                      "SEX": "M", "RACE": None})])
    assert rules(disc) == {"V-SITE"}


@pytest.mark.req("REQ-VAL-05")
def test_duplicate_key_keeps_first():
    v = DatasetValidator("VS", spec["datasets"]["VS"], spec, RUN_DATE, {"S01-001"})
    acc, disc = v.run([SourceRecord(1, dict(GOOD_VS)), SourceRecord(2, dict(GOOD_VS))])
    assert [a.record_no for a in acc] == [1]
    assert rules(disc) == {"V-DUP"} and disc[0].record_no == 2


@pytest.mark.req("REQ-VAL-06")
def test_cross_field_rule():
    _, disc, _ = vs(SYSBP="120", DIABP="125")
    assert rules(disc) == {"VS-CF-01"}


@pytest.mark.req("REQ-VAL-06")
def test_cross_field_skipped_when_operand_invalid():
    _, disc, _ = vs(SYSBP="abc", DIABP="125")      # only the type error, no misleading CF error
    assert rules(disc) == {"V-TYPE"}


@pytest.mark.req("REQ-VAL-07")
def test_future_date():
    _, disc, _ = vs(VS_DATE="2026-04-16")           # day after RUN_DATE
    assert rules(disc) == {"V-FUTURE"}


@pytest.mark.req("REQ-VAL-08")
def test_record_with_any_error_is_not_loaded():
    acc, disc, _ = vs(PULSE="abc")                  # everything else valid
    assert acc == [] and len(disc) == 1


@pytest.mark.req("REQ-VAL-08")
def test_warning_does_not_reject(monkeypatch):
    ds = dict(spec["datasets"]["VS"])
    ds["cross_field_rules"] = [{"id": "VS-CF-01", "rule": "DIABP < SYSBP", "severity": "warning"}]
    v = DatasetValidator("VS", ds, spec, RUN_DATE, {"S01-001"})
    acc, disc = v.run([SourceRecord(1, {**GOOD_VS, "SYSBP": "120", "DIABP": "125"})])
    assert len(acc) == 1 and disc[0].severity == "warning"
