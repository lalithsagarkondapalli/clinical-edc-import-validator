# AI-Assisted Development Statement

This project was built with an AI coding assistant (Claude) under my direction. I'm stating that
plainly, because the role this project targets asks for exactly this skill: using approved AI tools
productively **and** independently validating everything they produce.

## How the work was split
| Me | AI assistant |
|---|---|
| Chose the problem: the controlled clinical data transfer that comes *before* the analysis work I do at USF | Drafted most of the Python, XSD, XSLT, SQL and PowerShell code |
| Mapped the job requirements to features (the table in the README) | Drafted the synthetic data and the seeded-error cases |
| Set the scope, the rules and what "done" means (tests, CI, reconciliation) | Drafted documentation, which I edited |
| Reviewed the outputs and decided what to keep or change | Explained unfamiliar APIs (lxml XSLT, XSD `key`/`keyref`, SQL*Loader options) |

## How AI output was validated
I treat AI-generated code as unverified until independent evidence says otherwise:

- **Tests tied to requirements.** 50 pytest cases, each tagged to a requirement in
  `validation/requirements.yaml`. The build fails if any requirement has no test.
- **Positive and negative cases.** Every rule has a passing case and seeded failures, with boundary values
  tested explicitly (e.g. SYSBP 59 / 60 / 250 / 251).
- **Independent reconciliation.** Record counts are re-derived by XPath on the written file, by an XSLT
  flatten, and by SQL on a staging table. A bug in the generated ODM builder would show up as a
  reconciliation failure rather than passing silently.
- **Golden baseline.** The discrepancy report was checked against the seeded-error table in
  [VALIDATION_PLAN.md](VALIDATION_PLAN.md) before it was approved as the regression baseline.
- **CI on every push.** GitHub Actions runs the test suite on Python 3.10 and 3.12 and an end-to-end
  PowerShell run, and keeps the evidence as build artifacts.

## Data and governance
- All data is synthetic. No real patient data, credentials or proprietary specifications were given to the
  assistant.
- In a regulated setting I would use only the organisation's approved AI tools and follow its AI governance
  and change-control procedures.
