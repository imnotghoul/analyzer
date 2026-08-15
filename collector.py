import json
import re
import time
from pathlib import Path

from config import (
    CHECK_INTERVAL,
    CLICK_TEXTS_BEFORE_START,
    DEBUG_OUTPUT_FILE,
    FRAME_SELECTOR,
    HISTORY_BAR_MAX_Y,
    HISTORY_BAR_ONLY,
    MIN_HISTORY_VALUE,
    NUMBER_SELECTOR,
    OUTPUT_FILE,
    PREDICT_AFTER_EACH_NEW_EVENT,
    PREDICTION_FILE,
    READ_FROM_BODY_TEXT,
    REFRESH_PAGE,
    SAVE_INITIAL_HISTORY,
    SCAN_ALL_FRAMES,
    STATE_FILE,
    URL,
    WAIT_AFTER_CLICK,
)
from models import CollectorState

NUMBER_PATTERN = re.compile(r"(?<![\w.,-])(-?\d+(?:[.,]\d+)?)(?:\s*[xхXХ])?(?![\w.,])")
MULTIPLIER_TEXT_LOCATOR = r"text=/\b\d+(?:[\.,]\d+)?\s*[xхXХ]\b/"
BLOCK_TEXT_PATTERNS = (
    "captcha",
    "cloudflare",
    "access denied",
    "forbidden",
    "too many requests",
    "checking your browser",
    "challenge",
)


def extract_numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in NUMBER_PATTERN.findall(text):
        values.append(float(match.replace(",", ".")))
    return values


def collect_numbers_from_texts(texts: list[str]) -> list[float]:
    values: list[float] = []
    for text in texts:
        values.extend(extract_numbers(text))
    return values


def filter_top_bar_multiplier_items(items: list[tuple[str, dict | None]], max_y: int, min_value: float = 1.0) -> list[str]:
    texts: list[str] = []
    for text, box in items:
        if not box:
            continue
        numbers = extract_numbers(text)
        if box.get("y", 999999) <= max_y and numbers and numbers[0] >= min_value:
            texts.append(text)
    return texts


def collect_numbers_from_contexts(contexts, number_selector: str | None, read_body_text: bool) -> list[float]:
    values: list[float] = []
    for context in contexts:
        try:
            if read_body_text:
                values.extend(extract_numbers(context.locator("body").inner_text(timeout=3000)))
            elif number_selector:
                values.extend(collect_numbers_from_texts(context.locator(number_selector).all_inner_texts()))
        except Exception:
            continue
    return values


def normalize_optional_selector(selector: str) -> str | None:
    selector = selector.strip()
    if not selector or selector == ".replace-me":
        return None
    return selector


def click_texts_before_start(page, texts: list[str], wait_after_click: float = 2) -> list[str]:
    clicked: list[str] = []
    for text in texts:
        clean_text = text.strip()
        if not clean_text:
            continue
        if _click_text_in_any_context(page, clean_text):
            clicked.append(clean_text)
            if wait_after_click > 0:
                page.wait_for_timeout(int(wait_after_click * 1000))
        else:
            print(f"Не удалось найти текст для клика: {clean_text}")
    return clicked


def _click_text_in_any_context(page, text: str) -> bool:
    contexts = [page]
    contexts.extend(getattr(page, "frames", []))

    for context in contexts:
        try:
            context.get_by_text(text, exact=False).first.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


def format_number(value: float) -> str:
    return f"{value:.2f}"


def find_new_events(previous: list[float], current: list[float]) -> list[float]:
    if not previous:
        return current[:]
    if current == previous:
        return []

    match_index = _find_subsequence(current, previous)
    if match_index is not None:
        return current[:match_index]

    overlap_events = _find_events_with_dropped_tail(previous, current)
    if overlap_events is not None:
        return overlap_events

    common_prefix = 0
    max_prefix = min(len(previous), len(current))
    while common_prefix < max_prefix and previous[common_prefix] == current[common_prefix]:
        common_prefix += 1

    if common_prefix == len(previous):
        return current[len(previous):]

    if current and previous and current[0] != previous[0]:
        return [current[0]]

    return []


def _find_events_with_dropped_tail(previous: list[float], current: list[float]) -> list[float] | None:
    max_overlap = min(len(previous), len(current))
    for overlap in range(max_overlap, 0, -1):
        new_count = len(current) - overlap
        if current[new_count:] == previous[:overlap]:
            return current[:new_count]
    return None


def _find_subsequence(values: list[float], needle: list[float]) -> int | None:
    if len(needle) > len(values):
        return None
    for start in range(len(values) - len(needle) + 1):
        if values[start : start + len(needle)] == needle:
            return start
    return None


def load_state(path: str) -> CollectorState:
    state_path = Path(path)
    if not state_path.exists():
        return CollectorState()

    data = json.loads(state_path.read_text(encoding="utf-8"))
    return CollectorState(
        last_id=int(data.get("last_id", 0)),
        last_sequence=[float(value) for value in data.get("last_sequence", [])],
        processed_external_ids=[str(value) for value in data.get("processed_external_ids", [])],
    )


def save_state(path: str, state: CollectorState) -> None:
    state_path = Path(path)
    data = {
        "last_id": state.last_id,
        "last_sequence": state.last_sequence,
        "processed_external_ids": state.processed_external_ids,
    }
    state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_events(output_file: str, state: CollectorState, events: list[float]) -> None:
    if not events:
        return

    output_path = Path(output_file)
    with output_path.open("a", encoding="utf-8") as file:
        for value in events:
            state.last_id += 1
            file.write(f"{state.last_id} | {format_number(value)}\n")


def update_prediction_file(numbers_file: str, prediction_file: str) -> None:
    from analyzer import analyze_sequence, read_numbers_file

    numbers = read_numbers_file(numbers_file)
    output_path = Path(prediction_file)
    if not numbers:
        output_path.write_text("No numbers collected yet.\n", encoding="utf-8")
        return

    result = analyze_sequence(numbers)
    text = build_prediction_summary(numbers, result)
    output_path.write_text(text, encoding="utf-8")


def build_prediction_summary(numbers: list[float], result) -> str:
    range_line = _live_prediction_range(result)
    text = (
        f"Сколько чисел анализировано: {len(numbers)}\n"
        f"Последнее число: {format_number(numbers[-1])}\n"
        f"Предполагаемое следующее значение: {_live_prediction_value(result)}\n"
    )
    if range_line:
        text += f"Диапазон/зона: {range_line}\n"
    text += f"Уверенность: {_live_prediction_confidence(result)}\n"
    return text


def _live_prediction_value(result) -> str:
    if result.category_forecast and _numeric_forecast_is_too_noisy(result):
        return "нет надежного точного значения"
    return result.forecast_text or result._build_forecast_text()


def _live_prediction_range(result) -> str | None:
    if result.category_forecast:
        return result.category_forecast
    if result.forecast_low is not None and result.forecast_high is not None:
        return f"{format_number(result.forecast_low)}-{format_number(result.forecast_high)}"
    return None


def _live_prediction_confidence(result) -> str:
    if result.category_forecast and _numeric_forecast_is_too_noisy(result):
        return result.confidence
    return result.confidence


def _numeric_forecast_is_too_noisy(result) -> bool:
    if result.next_value is None:
        return True
    if result.forecast_low is not None and result.forecast_high is not None:
        return True
    if result.error_margin is None:
        return False
    return result.error_margin >= max(abs(result.next_value) * 0.75, 3.0)


def is_blocked_page(status: int | None, text: str) -> bool:
    if status in {403, 429}:
        return True
    lowered = text.lower()
    return any(pattern in lowered for pattern in BLOCK_TEXT_PATTERNS)


def run_collector() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright не установлен. Выполните: pip install -r requirements.txt")
        return

    state = load_state(STATE_FILE)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        click_texts_before_start(page, CLICK_TEXTS_BEFORE_START, WAIT_AFTER_CLICK)

        try:
            if _page_is_blocked(page, response.status if response else None):
                print("Доступ запрещен или страница показывает защиту. Обходить защиту программа не будет.")
                return

            initial_sequence = read_numbers_from_page(page)
            if not state.last_sequence:
                state.last_sequence = initial_sequence
                if SAVE_INITIAL_HISTORY:
                    append_events(OUTPUT_FILE, state, initial_sequence)
                    if PREDICT_AFTER_EACH_NEW_EVENT:
                        update_prediction_file(OUTPUT_FILE, PREDICTION_FILE)
                save_state(STATE_FILE, state)
                print(f"Начальное состояние сохранено. Значений найдено: {len(initial_sequence)}")

            while True:
                if REFRESH_PAGE:
                    response = page.reload(wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)
                    if _page_is_blocked(page, response.status if response else None):
                        print("Доступ запрещен или страница показывает защиту. Обходить защиту программа не будет.")
                        return

                current_sequence = read_numbers_from_page(page)
                events = find_new_events(state.last_sequence, current_sequence)
                append_events(OUTPUT_FILE, state, events)
                if events and PREDICT_AFTER_EACH_NEW_EVENT:
                    update_prediction_file(OUTPUT_FILE, PREDICTION_FILE)
                state.last_sequence = current_sequence
                save_state(STATE_FILE, state)

                if events:
                    print(f"Новых событий: {len(events)}")
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("Сбор остановлен пользователем.")
        finally:
            browser.close()


def read_numbers_from_page(page) -> list[float]:
    frame_selector = normalize_optional_selector(FRAME_SELECTOR)
    number_selector = normalize_optional_selector(NUMBER_SELECTOR)

    if HISTORY_BAR_ONLY:
        return read_top_bar_multipliers(page, HISTORY_BAR_MAX_Y, MIN_HISTORY_VALUE)

    if SCAN_ALL_FRAMES:
        return collect_numbers_from_contexts(page.frames, number_selector, READ_FROM_BODY_TEXT)

    if READ_FROM_BODY_TEXT:
        return collect_numbers_from_texts([page.locator("body").inner_text(timeout=3000)])

    if frame_selector and number_selector:
        frame = page.frame_locator(frame_selector)
        texts = frame.locator(number_selector).all_inner_texts()
        return collect_numbers_from_texts(texts)

    if number_selector:
        texts = page.locator(number_selector).all_inner_texts()
        return collect_numbers_from_texts(texts)

    return []


def read_top_bar_multipliers(page, max_y: int, min_value: float = 1.0) -> list[float]:
    texts: list[str] = []
    for context in page.frames:
        try:
            locator = context.locator(MULTIPLIER_TEXT_LOCATOR)
            count = locator.count()
        except Exception:
            continue

        items: list[tuple[str, dict | None]] = []
        for index in range(count):
            try:
                element = locator.nth(index)
                items.append((element.inner_text(timeout=1000), element.bounding_box(timeout=1000)))
            except Exception:
                continue
        texts.extend(filter_top_bar_multiplier_items(items, max_y, min_value))
    return collect_numbers_from_texts(texts)


def run_diagnostics() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright не установлен. Выполните: pip install -r requirements.txt")
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        clicked_texts = click_texts_before_start(page, CLICK_TEXTS_BEFORE_START, WAIT_AFTER_CLICK)

        try:
            status = response.status if response else None
            blocked = _page_is_blocked(page, status)
            title = page.title()
            body_text = _safe_body_text(page)
            body_numbers = extract_numbers(body_text)
            number_selector = normalize_optional_selector(NUMBER_SELECTOR)
            frame_selector = normalize_optional_selector(FRAME_SELECTOR)
            selector_count = _safe_count(page, number_selector) if number_selector else 0
            selector_numbers = read_numbers_from_page(page) if number_selector or READ_FROM_BODY_TEXT else []
            if HISTORY_BAR_ONLY:
                selector_numbers = read_top_bar_multipliers(page, HISTORY_BAR_MAX_Y, MIN_HISTORY_VALUE)
            canvas_count = _safe_count(page, "canvas")
            frame_lines = _describe_frames(page)

            report = [
                f"URL: {URL}",
                f"HTTP status: {status}",
                f"Title: {title}",
                f"Blocked/protection detected: {blocked}",
                f"NUMBER_SELECTOR: {NUMBER_SELECTOR}",
                f"FRAME_SELECTOR: {FRAME_SELECTOR or '(не задан)'}",
                f"SCAN_ALL_FRAMES: {SCAN_ALL_FRAMES}",
                f"READ_FROM_BODY_TEXT: {READ_FROM_BODY_TEXT}",
                f"HISTORY_BAR_ONLY: {HISTORY_BAR_ONLY}",
                f"HISTORY_BAR_MAX_Y: {HISTORY_BAR_MAX_Y}",
                f"CLICK_TEXTS_BEFORE_START: {CLICK_TEXTS_BEFORE_START}",
                f"Clicked texts before start: {clicked_texts}",
                f"Elements found by NUMBER_SELECTOR on main page: {selector_count}",
                f"Numbers found by current settings: {selector_numbers[:30]}",
                f"Numbers visible in body text: {body_numbers[:50]}",
                f"Canvas elements on main page: {canvas_count}",
                "Frames:",
                *frame_lines,
                "",
                "Body text sample:",
                body_text[:3000],
            ]
            Path(DEBUG_OUTPUT_FILE).write_text("\n".join(report), encoding="utf-8")

            print(f"Диагностика сохранена в {DEBUG_OUTPUT_FILE}")
            print(f"HTTP status: {status}")
            print(f"Элементов по NUMBER_SELECTOR: {selector_count}")
            print(f"Чисел по текущим настройкам: {len(selector_numbers)}")
            print(f"Чисел в видимом тексте страницы: {len(body_numbers)}")
            print(f"Canvas на странице: {canvas_count}")
            print(f"Iframe/frame найдено: {max(0, len(page.frames) - 1)}")

            if blocked:
                print("Похоже на защиту или запрет доступа. Обходить это программа не будет.")
            elif canvas_count and not body_numbers:
                print("Похоже, числа могут быть нарисованы на canvas. CSS-селектор тогда не увидит сами числа.")
            elif body_numbers and not selector_numbers:
                print("Числа есть в тексте страницы, но текущий селектор их не находит. Нужен другой NUMBER_SELECTOR или READ_FROM_BODY_TEXT = True.")
            elif page.frames and len(page.frames) > 1 and not selector_numbers:
                print("На странице есть iframe. Возможно, нужно задать FRAME_SELECTOR и селектор числа внутри фрейма.")
        finally:
            browser.close()


def _safe_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def _safe_count(page, selector: str | None) -> int:
    if not selector:
        return 0
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def _describe_frames(page) -> list[str]:
    lines: list[str] = []
    for index, frame in enumerate(page.frames):
        label = "main page" if index == 0 else f"frame {index}"
        try:
            text = frame.locator("body").inner_text(timeout=1000)
            numbers = extract_numbers(text)
        except Exception:
            numbers = []
        lines.append(f"- {label}: url={frame.url}, numbers_in_text={numbers[:20]}")
    return lines


def _page_is_blocked(page, status: int | None) -> bool:
    try:
        body_text = page.locator("body").inner_text(timeout=2000)
    except Exception:
        body_text = ""
    return is_blocked_page(status, body_text)
