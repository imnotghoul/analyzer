# Number Tracker Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small local Python project that collects dynamic numbers from a web page and analyzes numeric sequences.

**Architecture:** Keep the project flat and beginner-friendly. `collector.py` owns Playwright and persistence logic, `analyzer.py` owns sequence parsing and prediction, and `main.py` only coordinates menu choices.

**Tech Stack:** Python, Playwright, numpy, scipy, scikit-learn, pytest.

## Global Constraints

- Run locally with `python main.py`.
- Do not target any specific website.
- Read `URL` and `NUMBER_SELECTOR` from `config.py`.
- Do not add GUI, server, database, Docker, API, authorization, proxy, CAPTCHA bypass, Cloudflare bypass, or anti-bot bypass.
- Keep the code small and understandable for a beginner.

---

### Task 1: Collector Pure Logic

**Files:**
- Create: `collector.py`
- Create: `models.py`
- Test: `test_collector_logic.py`

**Interfaces:**
- Produces: `extract_numbers(text: str) -> list[float]`
- Produces: `find_new_events(previous: list[float], current: list[float]) -> list[float]`
- Produces: `format_number(value: float) -> str`

- [ ] Write failing tests for decimal parsing and duplicate-aware event detection.
- [ ] Run `python -m pytest test_collector_logic.py -v` and confirm expected failures.
- [ ] Implement the minimal pure functions.
- [ ] Run `python -m pytest test_collector_logic.py -v` and confirm passing output.

### Task 2: Analyzer Exact Rules

**Files:**
- Create: `analyzer.py`
- Modify: `models.py`
- Test: `test_analyzer.py`

**Interfaces:**
- Produces: `parse_manual_numbers(text: str) -> list[float]`
- Produces: `read_numbers_file(path: str) -> list[float]`
- Produces: `analyze_sequence(numbers: list[float]) -> AnalysisResult`
- Consumes: `AnalysisResult` from `models.py`

- [ ] Write failing tests for arithmetic, geometric, alternating differences, repeated values, and file parsing.
- [ ] Run `python -m pytest test_analyzer.py -v` and confirm expected failures.
- [ ] Implement exact rule detection and result formatting.
- [ ] Run `python -m pytest test_analyzer.py -v` and confirm passing output.

### Task 3: Analyzer ML Fallback

**Files:**
- Modify: `analyzer.py`
- Modify: `models.py`
- Test: `test_analyzer.py`

**Interfaces:**
- Produces: ML fallback inside `analyze_sequence(numbers: list[float]) -> AnalysisResult`.

- [ ] Write failing tests for noisy sequences and random-looking sequences.
- [ ] Run `python -m pytest test_analyzer.py -v` and confirm expected failures.
- [ ] Implement ordered train/test evaluation, baseline comparison, MAE, confidence labels, and explanations.
- [ ] Run `python -m pytest test_analyzer.py -v` and confirm passing output.

### Task 4: Playwright Collector Runtime

**Files:**
- Create: `config.py`
- Modify: `collector.py`
- Test: `test_collector_logic.py`

**Interfaces:**
- Produces: `run_collector() -> None`
- Produces: `load_state(path: str) -> CollectorState`
- Produces: `save_state(path: str, state: CollectorState) -> None`
- Consumes: `CollectorState` from `models.py`

- [ ] Write failing tests for state loading defaults and append formatting.
- [ ] Run `python -m pytest test_collector_logic.py -v` and confirm expected failures.
- [ ] Implement state persistence, output writing, blocking-page detection, and Playwright loop.
- [ ] Run `python -m pytest test_collector_logic.py -v` and confirm passing output.

### Task 5: CLI And Documentation

**Files:**
- Create: `main.py`
- Create: `requirements.txt`
- Create: `README.md`

**Interfaces:**
- Consumes: `run_collector()`, `read_numbers_file()`, `parse_manual_numbers()`, and `analyze_sequence()`.

- [ ] Implement the menu choices `1`, `2`, and `3`.
- [ ] Add requirements with `numpy`, `scipy`, `scikit-learn`, `playwright`, and `pytest`.
- [ ] Write README with setup, Playwright install, config, launch, selector search, collection, and analysis instructions.
- [ ] Run `python -m pytest -v`.
- [ ] Run a basic CLI smoke check where possible without opening a real site.
