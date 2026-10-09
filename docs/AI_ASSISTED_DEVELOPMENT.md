# AI-Assisted Development Statement

<!-- EDIT THIS FILE so it describes exactly what you did. Keep it honest — an interviewer may ask. -->

I used an AI coding assistant (Claude) while building this project, under the same rule I would
follow at work: **AI output is a draft; I am responsible for every line that ships.**

## What the assistant was used for
- Drafting boilerplate (argument parsing, CSV writers, the XSD skeleton).
- Suggesting edge cases for validation rules and seeded test data.
- Explaining unfamiliar APIs (lxml XSLT, XSD `key`/`keyref`, SQL*Loader options).

## How I reviewed and validated it
- Read and ran every function; rewrote parts I could not explain line by line.
- Every rule has positive **and** negative tests; boundary values are tested explicitly.
- Reconciliation is independent of the generated code (XPath, XSLT and SQL re-count the output),
  so an AI-introduced bug in the builder would surface as a reconciliation failure.
- The golden baseline was checked by hand against the seeded-error table in
  [VALIDATION_PLAN.md](VALIDATION_PLAN.md) before it was approved.

## What I did not do
- No real patient data, credentials or proprietary specifications were given to the assistant.
- No AI output was committed without review and a passing test run.
