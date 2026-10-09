# Change Control

How a change to the transfer spec or the code gets from request to release.

1. **Request** — open an issue describing the change and the spec section it touches
   (e.g. "lab vendor adds `hba1c_pct`; range 3–20 %"). Unclear or conflicting requirements
   are raised as questions on the issue *before* coding.
2. **Branch** — `feature/<issue>-short-name`. No direct commits to `main`.
3. **Implement** — update `specs/*.yaml` first; change code only if the spec cannot express it.
4. **Requirements + tests** — add/adjust the requirement in `validation/requirements.yaml` and
   at least one positive and one negative test tagged with its ID.
5. **Regression** — run `pytest`. If the golden discrepancy baseline changes, the PR must
   explain every added/removed discrepancy. Re-generate the baseline only when the change is
   intended:
   ```bash
   python -m edcimport run --spec specs/CARD301_transfer_spec.yaml --out out --run-date 2026-04-15 --run-id BASELINE
   cp out/BASELINE/discrepancies.csv tests/golden/discrepancy_baseline.csv
   ```
6. **Review** — PR reviewed by a second person (in a team setting); CI must be green.
7. **Release** — bump `edcimport/__init__.py` and `spec_version`, update `CHANGELOG.md`,
   tag `vX.Y.Z`. The tag + CI artifacts are the release evidence.
