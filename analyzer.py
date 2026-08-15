import re
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.metrics import mean_absolute_error
except ImportError:
    RandomForestRegressor = None
    LinearRegression = None
    Ridge = None
    mean_absolute_error = None

from models import AnalysisResult, format_display_number

NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")
EPS = 1e-8


def parse_manual_numbers(text: str) -> list[float]:
    normalized = text.replace(",", " ")
    return [float(match) for match in NUMBER_PATTERN.findall(normalized)]


def read_numbers_file(path: str) -> list[float]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    numbers: list[float] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        value_part = line.split("|", 1)[1]
        match = NUMBER_PATTERN.search(value_part)
        if match:
            numbers.append(float(match.group(0).replace(",", ".")))
    return numbers


def analyze_sequence(numbers: list[float]) -> AnalysisResult:
    values = [float(value) for value in numbers]
    if len(values) < 2:
        result = AnalysisResult(
            found_patterns=[],
            best_method="Not enough data",
            next_value=values[-1] if values else None,
            why="Need at least two numbers to search for a pattern.",
            confidence="low",
        )
        return _attach_bucket_forecast(values, result)

    exact = _find_exact_rule(values)
    if exact is not None:
        return _attach_bucket_forecast(values, exact)

    approximate = _find_approximate_linear(values)
    ml = _run_ml_fallback(values)
    if ml is None:
        return _attach_bucket_forecast(values, approximate or _low_confidence_baseline(values))

    if approximate and approximate.historical_error is not None:
        if ml.historical_error is None or approximate.historical_error <= ml.historical_error:
            return _attach_bucket_forecast(values, approximate)

    return _attach_bucket_forecast(values, ml)


def bucket_for_value(value: float) -> str:
    if value < 2:
        return "<2"
    if value < 10:
        return "2-10"
    return "10+"


def predict_next_bucket(numbers: list[float], max_context: int = 4) -> dict:
    values = [float(value) for value in numbers]
    if len(values) < 4:
        return {
            "bucket": None,
            "confidence": 0.0,
            "context": [],
            "counts": {},
            "why": "Need at least 4 numbers for bucket forecast.",
        }

    buckets = [bucket_for_value(value) for value in values]
    max_context = min(max_context, len(buckets) - 1)
    for size in range(max_context, 0, -1):
        context = buckets[-size:]
        counts: dict[str, int] = {}
        for index in range(0, len(buckets) - size):
            if buckets[index : index + size] == context:
                next_bucket = buckets[index + size]
                counts[next_bucket] = counts.get(next_bucket, 0) + 1
        if counts:
            bucket, count = max(counts.items(), key=lambda item: item[1])
            total = sum(counts.values())
            return {
                "bucket": bucket,
                "confidence": count / total * 100,
                "context": context,
                "counts": counts,
                "why": f"After context {' -> '.join(context)} history most often moved to {bucket}.",
            }

    recent = buckets[-min(30, len(buckets)) :]
    counts: dict[str, int] = {}
    for bucket in recent:
        counts[bucket] = counts.get(bucket, 0) + 1
    bucket, count = max(counts.items(), key=lambda item: item[1])
    total = sum(counts.values())
    return {
        "bucket": bucket,
        "confidence": count / total * 100,
        "context": [],
        "counts": counts,
        "why": "No repeated context found; using recent bucket frequency.",
    }


def _attach_bucket_forecast(values: list[float], result: AnalysisResult) -> AnalysisResult:
    forecast = predict_next_bucket(values)
    bucket = forecast["bucket"]
    if not bucket:
        return result

    counts = ", ".join(f"{name}: {count}" for name, count in sorted(forecast["counts"].items()))
    context = " -> ".join(forecast["context"]) if forecast["context"] else "recent frequency"
    result.category_forecast = f"{bucket} ({forecast['confidence']:.1f}%)"
    result.category_details = f"context: {context}; counts: {counts}; {forecast['why']}"
    return result


def _find_exact_rule(values: list[float]) -> AnalysisResult | None:
    if _all_close(values):
        return AnalysisResult(
            found_patterns=["Все значения повторяются."],
            best_method="Повторяющееся значение",
            next_value=values[-1],
            why=f"Каждое число равно {format_display_number(values[-1])}, поэтому следующим ожидается такое же значение.",
            confidence="очень высокая",
        )

    diffs = _differences(values)
    if _all_close(diffs):
        step = diffs[0]
        return AnalysisResult(
            found_patterns=[f"Разность между соседними числами постоянная: {format_display_number(step)}."],
            best_method="Арифметическая прогрессия",
            next_value=values[-1] + step,
            why=f"Каждый следующий элемент получается прибавлением {format_display_number(step)}.",
            confidence="очень высокая",
        )

    ratio = _constant_ratio(values)
    if ratio is not None:
        return AnalysisResult(
            found_patterns=[f"Отношение соседних чисел постоянное: {format_display_number(ratio)}."],
            best_method="Геометрическая прогрессия",
            next_value=values[-1] * ratio,
            why=f"Каждый элемент равен предыдущему умноженному на {format_display_number(ratio)}.",
            confidence="очень высокая",
        )

    cycle = _find_repeating_cycle(values)
    if cycle is not None:
        next_value = cycle[len(values) % len(cycle)]
        return AnalysisResult(
            found_patterns=[f"Повторяется цикл значений: {', '.join(format_display_number(x) for x in cycle)}."],
            best_method="Повторяющийся цикл значений",
            next_value=next_value,
            why="Следующее число взято из следующей позиции повторяющегося цикла.",
            confidence="очень высокая",
        )

    diff_cycle = _find_repeating_cycle(diffs)
    if diff_cycle is not None:
        next_diff = diff_cycle[len(diffs) % len(diff_cycle)]
        return AnalysisResult(
            found_patterns=[f"Повторяется цикл разностей: {', '.join(format_display_number(x) for x in diff_cycle)}."],
            best_method="Повторяющийся цикл разностей",
            next_value=values[-1] + next_diff,
            why=f"Следующая разность по циклу равна {format_display_number(next_diff)}.",
            confidence="очень высокая",
        )

    polynomial = _find_polynomial_rule(values)
    if polynomial is not None:
        return polynomial

    return None


def _find_approximate_linear(values: list[float]) -> AnalysisResult | None:
    if len(values) < 5:
        return None
    diffs = _differences(values)
    mean_diff = sum(diffs) / len(diffs)
    errors = [abs(diff - mean_diff) for diff in diffs]
    mae = sum(errors) / len(errors)
    scale = max(1.0, sum(abs(value) for value in values) / len(values))

    if mae / scale > 0.08:
        return None

    baseline_errors = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    baseline = sum(baseline_errors) / len(baseline_errors) if baseline_errors else None
    improvement = None
    if baseline and baseline > EPS:
        improvement = max(0.0, (baseline - mae) / baseline * 100)

    confidence = "относительно высокая" if improvement and improvement >= 25 else "средняя"
    return AnalysisResult(
        found_patterns=["Похожа на арифметическую прогрессию с небольшим шумом."],
        best_method="Приблизительная арифметическая закономерность",
        next_value=values[-1] + mean_diff,
        why=f"Средняя разность между соседними числами примерно {format_display_number(mean_diff)}.",
        historical_error=mae,
        baseline_error=baseline,
        improvement=improvement,
        confidence=confidence,
        forecast_type="примерно ±",
        error_margin=max(mae, 0.01),
    )


def _run_ml_fallback(values: list[float]) -> AnalysisResult | None:
    if not all([RandomForestRegressor, LinearRegression, Ridge, mean_absolute_error]):
        return _low_confidence_baseline(values)

    if len(values) < 14:
        return _low_confidence_baseline(values)

    best: dict | None = None
    for window in range(2, min(6, len(values) - 2) + 1):
        x, y = _make_window_dataset(values, window)
        if len(x) < 4:
            continue

        split = max(1, int(len(x) * 0.7))
        if split >= len(x):
            split = len(x) - 1

        x_train, x_test = x[:split], x[split:]
        y_train, y_test = y[:split], y[split:]
        if len(x_train) < 5 or len(x_test) < 3:
            continue
        baseline_pred = [row[-1] for row in x_test]
        baseline_error = float(mean_absolute_error(y_test, baseline_pred))

        models = [
            ("LinearRegression", LinearRegression()),
            ("Ridge", Ridge(alpha=1.0)),
            ("RandomForestRegressor", RandomForestRegressor(n_estimators=80, random_state=42)),
        ]
        for name, model in models:
            model.fit(x_train, y_train)
            predictions = model.predict(x_test)
            error = float(mean_absolute_error(y_test, predictions))
            if best is None or error < best["error"]:
                best = {
                    "name": name,
                    "model": model,
                    "window": window,
                    "error": error,
                    "baseline_error": baseline_error,
                }

    if best is None:
        return _low_confidence_baseline(values)

    model = best["model"]
    window = best["window"]
    last_window = [values[-window:]]
    next_value = float(model.predict(last_window)[0])
    baseline_error = best["baseline_error"]
    improvement = 0.0
    if baseline_error > EPS:
        improvement = (baseline_error - best["error"]) / baseline_error * 100

    typical_spread = _typical_spread(values)
    relative_error = best["error"] / max(typical_spread, 1.0)
    if improvement <= 10 or relative_error > 0.35:
        result = _low_confidence_baseline(values)
        result.historical_error = best["error"]
        result.baseline_error = baseline_error
        result.improvement = improvement
        result.why = (
            "Сложная модель не показала достаточно надежного преимущества на поздних проверочных данных.\n"
            "Убедительной закономерности не обнаружено.\n"
            "Предположение следующего значения имеет низкую надежность."
        )
        return result

    confidence = "относительно высокая" if improvement >= 30 else "средняя"
    why = _describe_model(best["name"], model, values[-window:])
    return AnalysisResult(
        found_patterns=[f"Обнаружена возможная зависимость от последних {window} значений."],
        best_method=f"ML: {best['name']}, окно {window}",
        next_value=next_value,
        why=why,
        historical_error=best["error"],
        baseline_error=baseline_error,
        improvement=improvement,
        confidence=confidence,
        forecast_type="примерно ±",
        error_margin=max(best["error"], 0.01),
    )


def _describe_model(name: str, model, last_values: list[float]) -> str:
    if hasattr(model, "coef_"):
        parts = []
        coefficients = list(model.coef_)
        for index, coefficient in enumerate(coefficients):
            lag = len(coefficients) - index
            parts.append(f"x[n-{lag}]={format_display_number(last_values[index])} * {coefficient:.4f}")
        return "Линейная модель сложила вклады последних значений:\n" + "\n".join(parts)

    if hasattr(model, "feature_importances_"):
        pairs = []
        importances = list(model.feature_importances_)
        for index, importance in sorted(enumerate(importances), key=lambda item: item[1], reverse=True):
            lag = len(importances) - index
            pairs.append(f"x[n-{lag}] = {format_display_number(last_values[index])}, важность {importance:.3f}")
        return "Наиболее важными для RandomForest оказались:\n" + "\n".join(pairs)

    return "Модель выбрана по меньшей MAE на более поздних проверочных значениях."


def _low_confidence_baseline(values: list[float]) -> AnalysisResult:
    low, high = _rough_range(values)
    next_value = (low + high) / 2
    return AnalysisResult(
        found_patterns=[],
        best_method="Baseline",
        next_value=next_value,
        why=(
            "Убедительной закономерности не обнаружено.\n"
            "Предположение следующего значения имеет низкую надежность.\n"
            "Поэтому безопаснее смотреть не на точное число, а на грубую зону последних значений."
        ),
        confidence="низкая",
        forecast_type="низкая надежность",
        forecast_low=low,
        forecast_high=high,
    )


def _rough_range(values: list[float]) -> tuple[float, float]:
    recent = values[-min(30, len(values)) :]
    low = min(recent)
    high = max(recent)
    if abs(high - low) <= EPS:
        padding = max(abs(low) * 0.05, 1.0)
        return low - padding, high + padding
    return low, high


def _typical_spread(values: list[float]) -> float:
    low, high = _rough_range(values)
    return high - low


def _make_window_dataset(values: list[float], window: int) -> tuple[list[list[float]], list[float]]:
    x = []
    y = []
    for index in range(window, len(values)):
        x.append(values[index - window : index])
        y.append(values[index])
    return x, y


def _differences(values: list[float]) -> list[float]:
    return [values[index] - values[index - 1] for index in range(1, len(values))]


def _all_close(values: list[float]) -> bool:
    return all(abs(value - values[0]) <= EPS for value in values)


def _constant_ratio(values: list[float]) -> float | None:
    if any(abs(value) <= EPS for value in values[:-1]):
        return None
    ratios = [values[index] / values[index - 1] for index in range(1, len(values))]
    if _all_close(ratios):
        return ratios[0]
    return None


def _find_repeating_cycle(values: list[float]) -> list[float] | None:
    if len(values) < 4:
        return None
    for size in range(1, len(values) // 2 + 1):
        cycle = values[:size]
        if all(abs(value - cycle[index % size]) <= EPS for index, value in enumerate(values)):
            return cycle
    return None


def _find_polynomial_rule(values: list[float]) -> AnalysisResult | None:
    layers = [values]
    current = values
    for order in range(1, min(5, len(values) - 1) + 1):
        current = _differences(current)
        layers.append(current)
        if len(current) >= 2 and _all_close(current):
            next_diff = current[-1]
            for previous_layer in reversed(layers[1:-1]):
                next_diff = previous_layer[-1] + next_diff
            next_value = values[-1] + next_diff
            return AnalysisResult(
                found_patterns=[f"Конечные разности порядка {order} постоянные."],
                best_method="Полиномиальная закономерность",
                next_value=next_value,
                why="Следующее значение рассчитано продолжением таблицы конечных разностей.",
                confidence="очень высокая",
            )
    return None
