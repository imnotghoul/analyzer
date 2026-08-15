from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CollectorState:
    last_id: int = 0
    last_sequence: list[float] = field(default_factory=list)
    processed_external_ids: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    found_patterns: list[str]
    best_method: str
    next_value: Optional[float]
    why: str
    historical_error: Optional[float] = None
    baseline_error: Optional[float] = None
    improvement: Optional[float] = None
    confidence: str = "низкая"
    forecast_type: str = "точное число"
    error_margin: Optional[float] = None
    forecast_low: Optional[float] = None
    forecast_high: Optional[float] = None
    forecast_text: Optional[str] = None
    category_forecast: Optional[str] = None
    category_details: Optional[str] = None

    def format(self) -> str:
        patterns = "\n".join(f"- {item}" for item in self.found_patterns) or "- Убедительной закономерности не обнаружено."
        next_value = self.forecast_text or self._build_forecast_text()
        historical_error = format_metric(self.historical_error)
        baseline_error = format_metric(self.baseline_error)
        improvement = "нет" if self.improvement is None else f"{self.improvement:.1f}%"

        result = (
            "Найденные закономерности:\n"
            f"{patterns}\n\n"
            "Лучший метод:\n"
            f"{self.best_method}\n\n"
            "Предполагаемое следующее значение:\n"
            f"{next_value}\n\n"
            "Почему:\n"
            f"{self.why}\n\n"
            "Историческая ошибка:\n"
            f"{historical_error}\n\n"
            "Baseline error:\n"
            f"{baseline_error}\n\n"
            "Улучшение:\n"
            f"{improvement}\n\n"
            "Уверенность:\n"
            f"{self.confidence}"
        )
        if self.category_forecast:
            result += (
                "\n\n"
                "Bucket forecast:\n"
                f"{self.category_forecast}\n\n"
                "Bucket details:\n"
                f"{self.category_details or 'not enough data'}"
            )
        return result

    def _build_forecast_text(self) -> str:
        if self.next_value is None:
            return "не удалось рассчитать"

        value = format_display_number(self.next_value)
        if self.forecast_type == "примерно ±" and self.error_margin is not None:
            return f"примерно {value} ± {format_display_number(self.error_margin)}"

        if self.forecast_low is not None and self.forecast_high is not None:
            low = format_display_number(self.forecast_low)
            high = format_display_number(self.forecast_high)
            if self.forecast_type == "низкая надежность":
                return f"Грубый диапазон: {low}-{high}, ориентир {value}"
            return f"{low}-{high}"

        return value


def format_display_number(value: Optional[float]) -> str:
    if value is None:
        return "нет"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def format_metric(value: Optional[float]) -> str:
    if value is None:
        return "нет"
    return f"{value:.4f}".rstrip("0").rstrip(".")
