# Validation Plan — edcimport v1.0.0

> Scope note: this is a portfolio project on **synthetic data**. The plan shows how I would
> structure validation evidence for a regulated data-transfer program; it is not a formal
> CSV (computer system validation) package and the tool is not a validated system.

## 1. Purpose
Show that, for the CARD-301 transfer spec, the tool loads only records that satisfy the spec,
reports every record it rejects with a reason, and produces an EDC import file whose content
reconciles exactly to the source.

## 2. Scope
| In scope | Out of scope |
|---|---|
| Reading CSV, Excel, JSON, XML sources | Writing directly into a production EDC |
| Mapping, transformation, validation rules in the spec | Medical coding (MedDRA/WHODrug) |
| ODM 1.3.2 output + outbound XSD | Full official CDISC ODM schema conformance |
| Reconciliation, audit trail, regression baseline | Electronic signatures, access control |

## 3. Approach
1. **Requirements** — `validation/requirements.yaml`, one ID per testable statement.
2. **Tests** — every test is tagged `@pytest.mark.req("REQ-…")`. `tests/test_traceability.py`
   fails the build if a requirement has no test or a test cites an unknown requirement.
3. **Positive and negative cases** — each rule has a passing case and at least one seeded
   failure, including boundaries (e.g. SYSBP 59/60/250/251).
4. **Reference dataset** — `data/source/` contains seeded errors (listed below). Its expected
   discrepancy output is the approved **golden baseline** (`tests/golden/`).
5. **Independent checks** — reconciliation never trusts the code under test:
   counts are re-derived by XPath on the written file, by an XSLT flatten, and by SQL on a
   staging table.

## 4. Seeded errors in the reference dataset
| Dataset | Record | Seeded issue | Expected rule |
|---|---|---|---|
| DM | 7 | Sex = `X` | V-CODE |
| DM | 9 | Birth date missing | V-REQ |
| DM | 10 | Duplicate of record 2 | V-DUP |
| DM | 11 | Subject S03-003 declared at site S02 | V-SITE |
| VS | 4 | SYSBP 300 | V-RANGE |
| VS | 6 | Duplicate subject/visit | V-DUP |
| VS | 7 | DIABP ≥ SYSBP | VS-CF-01 |
| VS | 8 | Pulse `abc` | V-TYPE |
| VS | 10 | Date `2026-13-40` | V-DATE |
| VS | 11 | Visit `Wk 12` not in visit map | V-VISIT |
| VS | 12, 16 | Subject's DM record was rejected | V-SUBJ-REF |
| VS | 13 | Weight unit `stone` | V-UNIT |
| VS | 14 | Date in 2099 | V-FUTURE |
| VS | 15 | Subject `S09-001` (no such site) | V-SUBJ-PATTERN |
| VS | 16 | SYSBP missing | V-REQ |
| LB | 3 | Glucose 750 mg/dL | V-RANGE |
| LB | 5 | Creatinine `0,9` (decimal comma) | V-TYPE |
| AE | 3 | Resolution before onset | AE-CF-01 |
| AE | 5 | Severity `Grade 2` | V-CODE |

Transformations exercised on accepted records: 4 date formats → ISO 8601, `Female`/`Male`/`Mild`/`false`
codelist decodes, 179 lb → 81.2 kg.

## 5. Acceptance criteria
- 100 % of tests pass on supported Python versions (CI matrix).
- Every requirement traced to ≥ 1 passing test (`out/test_evidence/traceability_matrix.md`).
- ODM output is valid against `schemas/odm1-3-2_import_subset.xsd`.
- Reconciliation status `PASS` for every dataset; SQL checks return zero rows.
- Audit trail verifies; any edit/delete/re-order is detected.
- Discrepancies equal the golden baseline.

## 6. Evidence produced per run
`out/<run_id>/`: `run_manifest.json` (input SHA-256s, versions, git commit), `audit_trail.jsonl`,
`discrepancies.csv`, `reconciliation.csv`, `odm_clinicaldata.xml`, `odm_long.csv`, `staging.db`.
CI also keeps `junit.xml` and the traceability matrix as build artifacts.

## 7. Deviations
Any failed test or reconciliation is investigated before release; the root cause and fix are
recorded in the PR and in `CHANGELOG.md`.
