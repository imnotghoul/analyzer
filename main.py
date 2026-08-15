import sys

from analyzer import analyze_sequence, parse_manual_numbers, read_numbers_file
from collector import run_collector, run_diagnostics
from config import OUTPUT_FILE


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if args:
        _run_command(args[0].strip().lower())
        return

    print("Choose mode:")
    print("1 - collect numbers from site into numbers.txt")
    print("2 - analyze numbers from numbers.txt")
    print("3 - paste sequence manually")
    print("4 - page and selector diagnostics")

    choice = input("Your choice: ").strip()

    if choice == "1":
        run_collector()
    elif choice == "2":
        numbers = read_numbers_file(OUTPUT_FILE)
        _print_analysis(numbers)
    elif choice == "3":
        print("Paste numbers separated by comma, spaces, or new lines.")
        text = input("Sequence: ")
        numbers = parse_manual_numbers(text)
        _print_analysis(numbers)
    elif choice == "4":
        run_diagnostics()
    else:
        print("Unknown mode. Run again and choose 1, 2, 3, or 4.")


def _run_command(command: str) -> None:
    if command in {"collect", "1"}:
        run_collector()
    elif command in {"analyze", "2"}:
        numbers = read_numbers_file(OUTPUT_FILE)
        _print_analysis(numbers)
    elif command in {"diagnose", "diagnostics", "4"}:
        run_diagnostics()
    else:
        print("Unknown command. Use: collect, analyze, diagnose.")


def _print_analysis(numbers: list[float]) -> None:
    if not numbers:
        print("Numbers not found.")
        return
    result = analyze_sequence(numbers)
    print()
    print(result.format())


if __name__ == "__main__":
    main()
