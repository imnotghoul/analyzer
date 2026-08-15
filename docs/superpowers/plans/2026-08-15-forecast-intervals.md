# Forecast Intervals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make analyzer output a realistic forecast form: exact value, approximate value with error margin, or rough range.

**Architecture:** Extend `AnalysisResult` with forecast metadata while keeping `analyzer.py` responsible for computing the forecast. Existing exact rules remain first priority; noisy and low-confidence cases gain interval text based on historical error or observed value spread.

**Tech Stack:** Python standard library, optional scikit-learn fallback already present, unittest.

## Global Constraints

- Run locally with `python main.py`.
- Keep the project small and understandable.
- Do not claim random sequences are predictable when historical evidence is weak.
- Prefer honest forecast ranges over fake precision.

---

### Task 1: Forecast Metadata

**Files:**
- Modify: `models.py`
- Modify: `test_analyzer.py`

**Interfaces:**
- `AnalysisResult.forecast_type: str`
- `AnalysisResult.error_margin: float | None`
- `AnalysisResult.forecast_low: float | None`
- `AnalysisResult.forecast_high: float | None`
- `AnalysisResult.forecast_text: str | None`

- [ ] Add failing tests for `примерно ±` and low-confidence range output.
- [ ] Update `AnalysisResult.format()` to print forecast text instead of only the raw number.

### Task 2: Analyzer Forecast Ranges

**Files:**
- Modify: `analyzer.py`
- Modify: `README.md`

**Interfaces:**
- Approximate arithmetic and ML results set `forecast_type="примерно ±"` and an error margin from historical MAE.
- Low-confidence baseline sets `forecast_type="низкая надежность"` and a rough range from recent values.

- [ ] Compute error margins from historical errors.
- [ ] Compute a rough range for chaotic sequences.
- [ ] Document the forecast formats in README.
- [ ] Run `python -m unittest -v test_collector_logic.py test_analyzer.py`.
