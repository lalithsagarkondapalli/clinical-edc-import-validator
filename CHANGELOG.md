# Changelog

Every change to the transfer spec or the tool follows [docs/CHANGE_CONTROL.md](docs/CHANGE_CONTROL.md):
bump the version, record it here, re-run the regression suite, re-approve the golden baseline only if the
change in flagged records is intended.

## [Unreleased]

## [1.0.0] - spec v1.0
### Added
- Readers for site uploads (CSV, Excel), central lab (JSON with header checks) and safety vendor (namespaced XML with inbound XSD).
- Spec-driven mapping to CDISC ODM 1.3.2 ItemOIDs: ISO 8601 dates, codelist decode, unit conversion before range checks.
- Record-level validation with stable rule IDs; file-level quarantine for structurally bad transfers.
- ODM output validated against an outbound XSD subset, including ItemDef/ItemData referential integrity.
- Three-way reconciliation: Python counts, independent XPath counts, XSLT round trip + SQL staging checks.
- Hash-chained audit trail, run manifest with input checksums, golden-baseline regression test.
- PowerShell scheduler wrapper; Oracle DDL and SQL*Loader control file (reference).
