"""Spec-driven transformation and validation.

Each source record is mapped to target ItemOIDs, normalised (dates -> ISO 8601,
codelist decode, unit conversion) and checked. Any *error* discrepancy rejects the
record; warnings are logged but the record still loads.

Rule IDs are stable so discrepancy reports can be compared run-to-run.
"""
from __future__ import annotations

import operator
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .readers import SourceRecord

INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")
CROSS_RE = re.compile(r"^\s*(\w+)\s*(<=|>=|<|>|==|!=)\s*(\w+)\s*$")
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt,
       ">=": operator.ge, "==": operator.eq, "!=": operator.ne}


@dataclass
class Discrepancy:
    dataset: str
    record_no: int | str
    subject: str | None
    key: str
    item: str
    rule_id: str
    severity: str
    value: str | None
    message: str


@dataclass
class TransformedRecord:
    dataset: str
    record_no: int
    subject: str
    site: str
    event_oid: str
    repeat_key: str
    items: dict[str, str] = field(default_factory=dict)        # ItemOID -> value
    typed: dict[str, object] = field(default_factory=dict)     # source name -> typed value


@dataclass
class TransformStats:
    dates_reformatted: int = 0
    codes_decoded: int = 0
    units_converted: int = 0


def parse_date(raw: str, formats: list[str], with_time: bool) -> str | None:
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return dt.strftime("%Y-%m-%dT%H:%M:%S") if with_time else dt.strftime("%Y-%m-%d")
    return None


class DatasetValidator:
    def __init__(self, name: str, ds: dict, spec: dict, run_date: date,
                 registered_subjects: set[str] | None):
        self.name, self.ds, self.spec = name, ds, spec
        self.run_date = run_date
        self.registered = registered_subjects
        self.subject_col = ds.get("subject_source", "SUBJID")
        self.pattern = re.compile(spec["subject_id_pattern"])
        self.date_formats = spec["date_formats"]
        self.stats = TransformStats()

    # ------------------------------------------------------------------ helpers
    def _d(self, rec, subject, key, item, rule, value, msg, sev="error"):
        return Discrepancy(self.name, rec.record_no, subject, key, item, rule, sev, value, msg)

    def _key(self, rec: SourceRecord) -> str:
        return "|".join(str(rec.values.get(k) or "") for k in self.ds["key"])

    # ------------------------------------------------------------------ main
    def run(self, records: list[SourceRecord]):
        accepted: list[TransformedRecord] = []
        discrepancies: list[Discrepancy] = []
        seen_keys: dict[str, int] = {}

        for rec in records:
            errs: list[Discrepancy] = []
            subject = rec.values.get(self.subject_col)
            key = self._key(rec)

            # ---- duplicate key (first occurrence wins, later ones rejected)
            if key in seen_keys:
                errs.append(self._d(rec, subject, key, ",".join(self.ds["key"]), "V-DUP", key,
                                    f"duplicate key; first seen at record {seen_keys[key]}"))
            else:
                seen_keys[key] = rec.record_no

            # ---- subject identity
            site = None
            if not subject:
                errs.append(self._d(rec, subject, key, self.subject_col, "V-REQ", None, "subject id missing"))
            elif not self.pattern.match(subject):
                errs.append(self._d(rec, subject, key, self.subject_col, "V-SUBJ-PATTERN", subject,
                                    f"subject id does not match {self.spec['subject_id_pattern']}"))
            else:
                site = subject.split("-")[0]
                if self.registered is not None and subject not in self.registered:
                    errs.append(self._d(rec, subject, key, self.subject_col, "V-SUBJ-REF", subject,
                                        "subject not registered in accepted DM"))
            if self.name == "DM" and subject and site:
                declared = rec.values.get("SITE")
                if declared not in self.spec["sites"]:
                    errs.append(self._d(rec, subject, key, "SITE", "V-SITE", declared, "unknown site"))
                elif declared != site:
                    errs.append(self._d(rec, subject, key, "SITE", "V-SITE", declared,
                                        f"site {declared} does not match subject prefix {site}"))

            # ---- visit / event
            event_oid = self.ds.get("fixed_event")
            if not event_oid:
                label = rec.values.get(self.ds["event_source"])
                event_oid = self.spec["visits"].get(label or "")
                if not event_oid:
                    errs.append(self._d(rec, subject, key, self.ds["event_source"], "V-VISIT", label,
                                        "visit label not in spec visit map"))

            # ---- items
            out = TransformedRecord(self.name, rec.record_no, subject or "", site or "",
                                    event_oid or "", "1")
            rk_src = self.ds.get("repeat_key_source")
            if rk_src:
                out.repeat_key = rec.values.get(rk_src) or ""
            for item in self.ds["items"]:
                errs.extend(self._item(rec, subject, key, item, out))

            # ---- cross-field rules (only when both operands parsed cleanly)
            for rule in self.ds.get("cross_field_rules", []):
                m = CROSS_RE.match(rule["rule"])
                left, op, right = m.groups()
                lv, rv = out.typed.get(left), out.typed.get(right)
                if lv is not None and rv is not None and not OPS[op](lv, rv):
                    errs.append(self._d(rec, subject, key, f"{left},{right}", rule["id"],
                                        f"{lv} / {rv}", f"cross-field rule failed: {rule['rule']}",
                                        rule.get("severity", "error")))

            discrepancies.extend(errs)
            if not any(e.severity == "error" for e in errs):
                accepted.append(out)
        return accepted, discrepancies

    def _item(self, rec, subject, key, item, out: TransformedRecord):
        src, oid, typ = item["source"], item["oid"], item["type"]
        raw = rec.values.get(src)
        errs = []
        if raw is None:
            if item.get("required"):
                errs.append(self._d(rec, subject, key, oid, "V-REQ", None, f"{src} is required"))
            return errs

        value: object = raw
        if typ == "integer":
            if not INT_RE.match(raw):
                return [self._d(rec, subject, key, oid, "V-TYPE", raw, "not an integer")]
            value = int(raw)
        elif typ == "float":
            if not FLOAT_RE.match(raw):
                return [self._d(rec, subject, key, oid, "V-TYPE", raw, "not a decimal number")]
            value = float(raw)
        elif typ in ("date", "datetime"):
            iso = parse_date(raw, self.date_formats, typ == "datetime")
            if iso is None:
                return [self._d(rec, subject, key, oid, "V-DATE", raw, "unparseable or invalid date")]
            if iso != raw:
                self.stats.dates_reformatted += 1
            if date.fromisoformat(iso[:10]) > self.run_date:
                return [self._d(rec, subject, key, oid, "V-FUTURE", raw, "date is after the run date")]
            value = iso
        elif typ == "code":
            decoded = item["codelist"].get(raw)
            if decoded is None:
                return [self._d(rec, subject, key, oid, "V-CODE", raw,
                                f"not in codelist {sorted(set(item['codelist'].values()))}")]
            if decoded != raw:
                self.stats.codes_decoded += 1
            value = decoded
        elif typ == "text":
            if item.get("max_length") and len(raw) > item["max_length"]:
                return [self._d(rec, subject, key, oid, "V-LEN", raw, f"longer than {item['max_length']}")]

        # unit conversion before range check, so the range is always in target units
        if "unit_source" in item:
            unit = rec.values.get(item["unit_source"])
            factor = item["conversions"].get(unit or "")
            if factor is None:
                return [self._d(rec, subject, key, oid, "V-UNIT", unit,
                                f"unit not in {sorted(item['conversions'])}")]
            if unit != item["target_unit"]:
                value = round(float(value) * factor, 1)
                self.stats.units_converted += 1

        if "range" in item:
            lo, hi = item["range"]
            if not (lo <= value <= hi):
                errs.append(self._d(rec, subject, key, oid, "V-RANGE", raw, f"outside [{lo}, {hi}]"))
                return errs

        out.items[oid] = str(value)
        out.typed[src] = value
        return errs
