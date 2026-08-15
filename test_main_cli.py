import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main


class MainCliTest(unittest.TestCase):
    def test_collect_argument_runs_collector_without_prompt(self):
        with patch("main.run_collector") as run_collector:
            main.main(["collect"])

        run_collector.assert_called_once_with()

    def test_no_argument_keeps_interactive_menu(self):
        with patch("builtins.input", return_value="2"), patch("main.read_numbers_file", return_value=[]):
            output = io.StringIO()
            with redirect_stdout(output):
                main.main([])

        self.assertIn("1 -", output.getvalue())


if __name__ == "__main__":
    unittest.main()
