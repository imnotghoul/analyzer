# Number Tracker Analyzer Design

## Goal

Create a small local Python project that runs with `python main.py`, collects dynamically rendered numbers from a web page into `numbers.txt`, and analyzes saved or manually entered sequences to suggest the next value.

## Scope

The project stays local and beginner-friendly. It does not include a GUI, server, database, Docker, API, login flow, proxies, or bypass logic for CAPTCHA, Cloudflare, anti-bot pages, HTTP 403, or HTTP 429.

## Files

- `main.py`: console menu and user input.
- `config.py`: editable settings for URL, selector, interval, refresh mode, output file, and state file.
- `collector.py`: Playwright collection, number extraction, event comparison, state and output writing.
- `analyzer.py`: exact pattern detection, ML fallback, result formatting, and file/manual parsing.
- `models.py`: simple dataclasses used by collector and analyzer.
- `requirements.txt`: `numpy`, `scipy`, `scikit-learn`, `playwright`, and `pytest`.
- `test_analyzer.py`: analyzer tests.
- `test_collector_logic.py`: collector parsing and event-detection tests.
- `README.md`: beginner instructions.

## Collector Design

The collector opens `URL` with Playwright and reads all elements matching `NUMBER_SELECTOR`. It extracts decimal numbers from element text, supporting both dot and comma decimal separators. On first run, current DOM values become the known sequence. If `SAVE_INITIAL_HISTORY` is true, they are also appended to `numbers.txt`; otherwise they are only stored in `state.json`.

New events are detected by comparing the previous known sequence and the current sequence as ordered lists, preserving duplicates. The numeric value is not treated as a unique id. When the current sequence starts with newly inserted values and then contains the previous sequence, those inserted values are recorded. If the previous sequence is found elsewhere inside the current sequence, values before it are recorded. If the old sequence cannot be matched, only values that are clearly appended after the common prefix are recorded; otherwise the state is refreshed without writing uncertain duplicates.

Each saved event receives the next local id and is written as `ID | value`. `state.json` stores `last_id`, `last_sequence`, and `processed_external_ids`.

If a blocking response is detected, including HTTP 403, HTTP 429, obvious CAPTCHA text, Cloudflare challenge text, or an access-denied page, the collector stops with a clear message and does not try to bypass protection.

## Analyzer Design

The analyzer accepts any list of numbers. From `numbers.txt`, it reads only the value after `|`. Manual input accepts commas, spaces, and line breaks.

Exact rules have priority over ML:

- arithmetic progression;
- geometric progression;
- repeated same value;
- repeated value cycle;
- repeated difference cycle;
- second-order and higher finite-difference polynomial patterns;
- simple dependency from several previous values when an exact repeating relation is visible.

If no exact rule is found, the analyzer tries approximate and ML methods. It uses window sizes from 2 to 6 when enough data exists, preserves time order for train/test splitting, and compares `LinearRegression`, `Ridge`, and `RandomForestRegressor` against a baseline where the next value equals the previous value. MAE is the main error.

If the ML result is not better than baseline, the program says that no convincing pattern was found. If a model is better, the output includes the predicted next value, historical MAE, baseline MAE, improvement, confidence label, and a short explanation. Linear models show coefficients; RandomForest shows feature importances.

## Testing

Tests cover arithmetic progression, geometric progression, alternating difference pattern, noisy sequence fallback, random sequence behavior, reading `numbers.txt`, number extraction, and duplicate-aware new event detection.
