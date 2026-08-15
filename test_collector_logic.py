import unittest

from collector import (
    append_events,
    build_prediction_summary,
    collect_numbers_from_texts,
    collect_numbers_from_contexts,
    filter_top_bar_multiplier_items,
    click_texts_before_start,
    extract_numbers,
    find_new_events,
    format_number,
    load_state,
    normalize_optional_selector,
    update_prediction_file,
)
from models import AnalysisResult


class CollectorLogicTest(unittest.TestCase):
    def test_extract_numbers_supports_dot_and_comma_decimals(self):
        text = "values: 1 1.00 2,20 and 15.43"

        self.assertEqual(extract_numbers(text), [1.0, 1.0, 2.20, 15.43])

    def test_collect_numbers_from_texts_reads_multiple_dom_texts(self):
        texts = ["x 1.25", "nothing", "2,50 and 3"]

        self.assertEqual(collect_numbers_from_texts(texts), [1.25, 2.50, 3.0])

    def test_normalize_optional_selector_treats_empty_placeholder_as_none(self):
        self.assertIsNone(normalize_optional_selector(""))
        self.assertIsNone(normalize_optional_selector("   "))
        self.assertIsNone(normalize_optional_selector(".replace-me"))
        self.assertEqual(normalize_optional_selector("iframe.game"), "iframe.game")

    def test_click_texts_before_start_clicks_visible_texts_in_order(self):
        page = FakePage()

        clicked = click_texts_before_start(page, ["Демо-режим", "История"], wait_after_click=0)

        self.assertEqual(clicked, ["Демо-режим", "История"])
        self.assertEqual(page.clicked_texts, ["Демо-режим", "История"])

    def test_collect_numbers_from_contexts_can_scan_all_frames(self):
        contexts = [
            FakeSearchContext(["main has no target"]),
            FakeSearchContext(["history 1.27x 3.46x"]),
            FakeSearchContext(["next 2.53x"]),
        ]

        values = collect_numbers_from_contexts(contexts, None, read_body_text=True)

        self.assertEqual(values, [1.27, 3.46, 2.53])

    def test_filter_top_bar_multiplier_items_keeps_only_items_above_max_y(self):
        items = [
            ("0.00x", {"x": 1, "y": 84, "width": 58, "height": 26}),
            ("1.27x", {"x": 10, "y": 84, "width": 58, "height": 26}),
            ("3.46x", {"x": 80, "y": 84, "width": 58, "height": 26}),
            ("27.54x", {"x": 1333, "y": 500, "width": 64, "height": 26}),
            ("bad", {"x": 1, "y": 50, "width": 10, "height": 10}),
        ]

        self.assertEqual(filter_top_bar_multiplier_items(items, max_y=140, min_value=1.0), ["1.27x", "3.46x"])

    def test_find_new_events_detects_new_value_inserted_before_previous_sequence(self):
        previous = [8.40, 2.20, 15.70, 3.10]
        current = [6.80, 8.40, 2.20, 15.70, 3.10]

        self.assertEqual(find_new_events(previous, current), [6.80])

    def test_find_new_events_detects_new_value_when_fixed_bar_drops_old_tail(self):
        previous = [8.40, 2.20, 15.70, 3.10]
        current = [6.80, 8.40, 2.20, 15.70]

        self.assertEqual(find_new_events(previous, current), [6.80])

    def test_find_new_events_keeps_repeated_equal_values_as_events(self):
        previous = [2.20, 8.40, 15.70]
        current = [2.20, 2.20, 8.40, 15.70]

        self.assertEqual(find_new_events(previous, current), [2.20])

    def test_find_new_events_uses_leftmost_value_when_bar_changed_without_overlap(self):
        previous = [8.40, 2.20, 15.70, 3.10]
        current = [1.22, 6.80, 4.40, 9.90]

        self.assertEqual(find_new_events(previous, current), [1.22])

    def test_format_number_uses_two_decimals(self):
        self.assertEqual(format_number(2), "2.00")
        self.assertEqual(format_number(15.437), "15.44")

    def test_load_state_returns_defaults_when_file_does_not_exist(self):
        state = load_state("__missing_state_for_test.json")

        self.assertEqual(state.last_id, 0)
        self.assertEqual(state.last_sequence, [])
        self.assertEqual(state.processed_external_ids, [])

    def test_append_events_writes_ids_and_values(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "numbers.txt"
            state = load_state(str(Path(temp_dir) / "missing.json"))

            append_events(str(output_file), state, [2.2, 5.31, 2.2])

            self.assertEqual(
                output_file.read_text(encoding="utf-8").splitlines(),
                ["1 | 2.20", "2 | 5.31", "3 | 2.20"],
            )
            self.assertEqual(state.last_id, 3)

    def test_update_prediction_file_reads_accumulated_numbers(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            numbers_file = Path(temp_dir) / "numbers.txt"
            prediction_file = Path(temp_dir) / "prediction.txt"
            numbers_file.write_text(
                "\n".join(
                    [
                        "1 | 12.00",
                        "2 | 1.20",
                        "3 | 1.40",
                        "4 | 3.20",
                        "5 | 15.00",
                        "6 | 1.10",
                        "7 | 1.80",
                        "8 | 4.00",
                        "9 | 18.00",
                        "10 | 1.30",
                        "11 | 1.50",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            update_prediction_file(str(numbers_file), str(prediction_file))

            text = prediction_file.read_text(encoding="utf-8")
            self.assertIn("Сколько чисел анализировано: 11", text)
            self.assertIn("Последнее число: 1.50", text)
            self.assertIn("Предполагаемое следующее значение:", text)
            self.assertIn("Уверенность:", text)
            self.assertIn("2-10", text)
            self.assertNotIn("Bucket details", text)
            self.assertNotIn("Почему", text)
    def test_prediction_summary_keeps_value_separate_from_range(self):
        result = AnalysisResult(
            found_patterns=[],
            best_method="Baseline",
            next_value=78.37,
            why="too noisy",
            confidence="low",
            forecast_low=1.0,
            forecast_high=155.75,
            category_forecast="10+ (50.0%)",
        )

        text = build_prediction_summary([1.1, 1.2, 1.3], result)
        lines = text.splitlines()

        self.assertIn("нет надежного точного значения", lines[2])
        self.assertNotIn("10+", lines[2])
        self.assertIn("Диапазон/зона: 10+ (50.0%)", text)


if __name__ == "__main__":
    unittest.main()


class FakePage:
    def __init__(self):
        self.clicked_texts = []

    def get_by_text(self, text, exact=True):
        return FakeLocator(self, text)

    def wait_for_timeout(self, milliseconds):
        pass


class FakeLocator:
    def __init__(self, page, text):
        self.page = page
        self.text = text

    @property
    def first(self):
        return self

    def click(self, timeout):
        self.page.clicked_texts.append(self.text)


class FakeSearchContext:
    def __init__(self, texts):
        self.texts = texts

    def locator(self, selector):
        return FakeTextLocator(self.texts)


class FakeTextLocator:
    def __init__(self, texts):
        self.texts = texts

    def inner_text(self, timeout=3000):
        return "\n".join(self.texts)

    def all_inner_texts(self):
        return self.texts
