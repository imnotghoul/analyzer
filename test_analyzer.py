import tempfile
import unittest
from pathlib import Path

from analyzer import analyze_sequence, parse_manual_numbers, predict_next_bucket, read_numbers_file


class AnalyzerTest(unittest.TestCase):
    def test_parse_manual_numbers_accepts_commas_spaces_and_newlines(self):
        text = "3, 7, 5\n9 7,11"

        self.assertEqual(parse_manual_numbers(text), [3.0, 7.0, 5.0, 9.0, 7.0, 11.0])

    def test_read_numbers_file_takes_only_value_after_pipe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "numbers.txt"
            file_path.write_text("1 | 2.20\n2 | 5.31\nbad line\n3 | 2,20\n", encoding="utf-8")

            self.assertEqual(read_numbers_file(str(file_path)), [2.20, 5.31, 2.20])

    def test_analyze_arithmetic_progression_predicts_next_value(self):
        result = analyze_sequence([2, 5, 8, 11, 14])

        self.assertEqual(result.best_method, "Арифметическая прогрессия")
        self.assertEqual(result.next_value, 17)
        self.assertEqual(result.confidence, "очень высокая")

    def test_analyze_geometric_progression_predicts_next_value(self):
        result = analyze_sequence([2, 4, 8, 16, 32])

        self.assertEqual(result.best_method, "Геометрическая прогрессия")
        self.assertEqual(result.next_value, 64)
        self.assertEqual(result.confidence, "очень высокая")

    def test_analyze_repeating_difference_cycle_predicts_next_value(self):
        result = analyze_sequence([3, 7, 5, 9, 7, 11, 9, 13])

        self.assertEqual(result.best_method, "Повторяющийся цикл разностей")
        self.assertEqual(result.next_value, 11)
        self.assertEqual(result.confidence, "очень высокая")

    def test_analyze_noisy_sequence_uses_model_or_approximation(self):
        result = analyze_sequence([2.0, 4.1, 6.0, 8.2, 10.1, 12.0, 14.2, 16.1, 18.0])

        self.assertIsNotNone(result.next_value)
        self.assertIn(result.confidence, {"относительно высокая", "средняя", "низкая"})
        self.assertIn("ошибка", result.format().lower())
        self.assertEqual(result.forecast_type, "примерно ±")
        self.assertIn("±", result.format())

    def test_analyze_random_sequence_reports_low_confidence(self):
        result = analyze_sequence([4, 19, 3, 27, 8, 31, 2, 24, 11, 29])

        self.assertIsNotNone(result.next_value)
        self.assertEqual(result.confidence, "низкая")
        self.assertEqual(result.forecast_type, "низкая надежность")
        self.assertIsNotNone(result.forecast_low)
        self.assertIsNotNone(result.forecast_high)
        self.assertIn("Убедительной закономерности не обнаружено", result.format())
        self.assertIn("Грубый диапазон", result.format())
    def test_predict_next_bucket_learns_transition_after_high_and_two_lows(self):
        numbers = [
            12.0, 1.2, 1.4, 3.2,
            15.0, 1.1, 1.8, 4.0,
            18.0, 1.3, 1.5,
        ]

        forecast = predict_next_bucket(numbers)

        self.assertEqual(forecast["bucket"], "2-10")
        self.assertGreaterEqual(forecast["confidence"], 60.0)

    def test_analyze_sequence_includes_bucket_forecast(self):
        numbers = [
            12.0, 1.2, 1.4, 3.2,
            15.0, 1.1, 1.8, 4.0,
            18.0, 1.3, 1.5,
        ]

        result = analyze_sequence(numbers)

        self.assertIn("2-10", result.category_forecast)
        self.assertIn("Bucket forecast", result.format())


if __name__ == "__main__":
    unittest.main()
