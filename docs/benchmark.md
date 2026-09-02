# AI Benchmark

The repository benchmark is a deterministic engineering safety suite, not a clinical validation
study. Its cases are wholly synthetic and must not contain identifiable or reconstructed patient
information.

## Current suite

The suite contains 50 cases spanning colon, rectal, and gastric cancer records. It exercises:

- postoperative recovery, pathology review, adjuvant evaluation, active treatment, surveillance,
  and unknown journey states;
- ordinary education/navigation questions;
- emergency-pattern detection in either the question or recorded symptom list;
- refusal of requests for an individualized drug, regimen, dose, switch, or discontinuation;
- hybrid retrieval against synthetic, reviewed fixtures; and
- machine-verifiable page citations.

The runner reports journey accuracy, safety accuracy, retrieval Recall@K, citation validity,
refusal accuracy, and dangerous-advice rate. CI requires at least 50 total cases and at least 10
retrieval cases, with all current deterministic expectations passing.

## Interpretation limits

A perfect score only means the current rule-based implementation matches these declared synthetic
expectations. It does not demonstrate diagnostic accuracy, treatment appropriateness, real-world
generalization, usability, fairness, or improved clinical outcomes. The fixtures intentionally
avoid recommending treatments and do not encode guideline claims.

Before a real deployment, independent clinical, patient-safety, privacy, accessibility, security,
and human-factors evaluation is required. Future evaluation sets should be versioned, reviewed by
qualified domain experts, stratified by cancer type and user group, checked for leakage, and kept
separate from development fixtures.
