"""Crawl public PTT rental-board threads and convert them into LeasePulse forum evidence.

Outputs:
  data/raw/ptt_threads.jsonl
  data/processed/forum_signals_real.json
  data/processed/forum_signals_real.csv

Example:
  python scripts/collect_ptt_forum_signals.py \
    --boards Rent_apart rent_tao Rent_ya home-sale \
    --max-pages 3 \
    --sleep 1.0 \
    --taipei-only \
    --since-years 2 \
    --output data/processed/forum_signals_real.json

Notes:
  - Use this only on publicly visible PTT pages.
  - Keep request rate low and respect robots.txt / site terms.
  - The script redacts common phone numbers and emails from stored content.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib import robotparser

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.ptt.cc"
DEFAULT_BOARDS = ["Rent_apart", "rent_tao", "Rent_ya", "home-sale"]

TAIPEI_DISTRICTS = [
    "中正", "大同", "中山", "松山", "大安", "萬華", "信義", "士林", "北投", "內湖", "南港", "文山",
]
NEW_TAIPEI_DISTRICTS = [
    "板橋", "三重", "中和", "永和", "新莊", "新店", "土城", "蘆洲", "汐止", "樹林", "淡水", "五股",
    "泰山", "林口", "深坑", "石碇", "坪林", "三峽", "鶯歌", "瑞芳", "八里", "金山", "萬里",
]
ALL_DISTRICTS = TAIPEI_DISTRICTS + NEW_TAIPEI_DISTRICTS

KEYWORD_PATTERNS = {
    "pricing": r"租金|房租|價格|價錢|開價|月租|租多少",
    "reasonable": r"合理|划算|太貴|太高|貴嗎|便宜|行情",
    "comparable": r"比較|參考|附近|周邊|同區|實價|行情",
    "vacancy": r"空租|空置|租不掉|沒人看|降租",
    "landlord": r"房東|出租|租客|租約",
    "tool": r"工具|網站|平台|app|APP|系統|估價",
    "elevator": r"電梯|華廈|大樓",
    "walkup": r"公寓|爬樓梯|無電梯",
    "studio": r"套房|雅房|分租|整層|獨立",
    "renovation": r"裝潢|翻新|整理|新裝",
}

MONTHLY_RENT_LABEL_RE = re.compile(
    r"每月租金[：:\s]*(?P<num>[\d,.]+(?:\.\d{3})?|\d+(?:\.\d+)?[万萬](?:\d+)?)",
    re.IGNORECASE,
)
GENERIC_MONEY_RE = re.compile(
    r"(?P<label>租金|房租|月租|價格|價錢|開價)[：:\s]*(?P<num>[\d,.]+(?:\.\d{3})?|\d+(?:\.\d+)?[万萬](?:\d+)?)",
    re.IGNORECASE,
)
WAN_MONEY_RE = re.compile(r"(?P<wan>\d+(?:\.\d+)?)[万萬](?P<extra>\d+)?")
DOT_THOUSANDS_RE = re.compile(r"(?<!\d)(?P<num>\d{1,2}\.\d{3})(?!\d)")
COMMA_MONEY_RE = re.compile(r"(?<!\d)(?P<num>\d{1,3}(?:,\d{3})+)(?:\s*(?:元|塊|/月|／月|月))?(?!\d)")
PLAIN_MONEY_RE = re.compile(r"(?<!\d)(?P<num>\d{4,6})(?:\s*(?:元|塊|/月|／月|月))?(?!\d)")
AREA_RE = re.compile(r"(?P<area>\d+(?:\.\d+)?)\s*(?:坪|ping|p)\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:09\d{2}[-\s]?\d{3}[-\s]?\d{3}|\d{2,4}[-\s]?\d{6,8})(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LINE_RE = re.compile(r"(?i)(line\s*(?:id|帳號)?\s*[:：]?\s*)[A-Za-z0-9_.-]{4,}")


@dataclass
class PTTArticle:
    thread_id: str
    board: str
    title: str
    author: str | None
    date: str | None
    posted_at: str | None = None
    url: str = ""
    short_snippet: str = ""
    contains_pricing_question: bool = False
    keywords: list[str] = field(default_factory=list)
    districts: list[str] = field(default_factory=list)
    extracted_prices_ntd: list[int] = field(default_factory=list)
    extracted_areas_ping: list[float] = field(default_factory=list)


def parse_ptt_datetime(date_str: str | None, reference: datetime | None = None) -> datetime | None:
    """Parse PTT article timestamps such as 'Wed Jul 26 21:06:35 2017' or index '7/26'."""
    if not date_str:
        return None

    reference = reference or datetime.now()
    text = date_str.strip()

    for fmt in ("%a %b %d %H:%M:%S %Y", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    index_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if index_match:
        # Index pages often omit the year; require article-page timestamps instead.
        return None

    return None


def resolve_since_date(
    since_date: str | None = None,
    since_years: float | None = 2.0,
) -> datetime | None:
    if since_date:
        return datetime.strptime(since_date, "%Y-%m-%d")
    if since_years is None:
        return None
    return datetime.now() - timedelta(days=int(since_years * 365.25))


def is_recent_enough(date_str: str | None, since_date: datetime | None) -> bool:
    if since_date is None:
        return True
    parsed = parse_ptt_datetime(date_str)
    if parsed is None:
        return False
    return parsed >= since_date


def parse_money_token(token: str) -> int | None:
    token = token.strip().replace(" ", "")
    if not token:
        return None

    wan_match = WAN_MONEY_RE.search(token)
    if wan_match:
        value = float(wan_match.group("wan")) * 10000
        extra = wan_match.group("extra")
        if extra:
            value += int(extra) * 1000
        return int(round(value))

    if re.fullmatch(r"\d+\.\d{3}", token):
        return int(token.replace(".", ""))

    if "," in token:
        try:
            return int(token.replace(",", ""))
        except ValueError:
            return None

    if re.fullmatch(r"\d+(?:\.\d+)?[kK]", token):
        return int(round(float(token[:-1]) * 1000))

    if token.endswith("千"):
        return int(round(float(token[:-1]) * 1000))

    try:
        return int(float(token))
    except ValueError:
        return None


def is_plausible_rent(value: int) -> bool:
    return 2000 <= value <= 300000


def is_pricing_question(text: str) -> bool:
    if re.search(r"[?？]", text) and re.search(KEYWORD_PATTERNS["pricing"], text, flags=re.IGNORECASE):
        return True
    question_words = r"多少|合理|行情|太貴|太高|便宜|估價|怎麼定|如何定|會不會太貴"
    return bool(
        re.search(question_words, text, flags=re.IGNORECASE)
        and re.search(KEYWORD_PATTERNS["pricing"], text, flags=re.IGNORECASE)
    )


def make_session(over18: bool = False) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; LeasePulseTaipeiAcademicCrawler/1.0; "
                "+https://github.com/FettHsiao/bdfinal)"
            )
        }
    )
    if over18:
        session.cookies.set("over18", "1", domain="www.ptt.cc")
    return session


def allowed_by_robots(
    url: str,
    user_agent: str = "LeasePulseTaipeiAcademicCrawler/1.0",
) -> bool:
    """Best-effort robots.txt check. If robots.txt cannot be fetched, allow throttled access."""
    rp = robotparser.RobotFileParser()
    rp.set_url(urljoin(BASE_URL, "/robots.txt"))
    try:
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as exc:
        print(f"[WARN] robots.txt unavailable ({exc}); continuing with throttled public-page access")
        return True


def get_html(session: requests.Session, url: str, sleep_seconds: float, retries: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        time.sleep(sleep_seconds + random.uniform(0, sleep_seconds * 0.3))
        try:
            response = session.get(url, timeout=20)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"[WARN] request failed ({attempt + 1}/{retries}) for {url}: {exc}")
            time.sleep(sleep_seconds * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}") from last_error


def parse_index_page(html: str, board: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[dict] = []

    for ent in soup.select("div.r-ent"):
        title_tag = ent.select_one("div.title a")
        if not title_tag or not title_tag.get("href"):
            continue
        title = title_tag.get_text(strip=True)
        href = title_tag["href"]
        author_tag = ent.select_one("div.author")
        date_tag = ent.select_one("div.date")
        articles.append(
            {
                "board": board,
                "title": title,
                "url": urljoin(BASE_URL, href),
                "author": author_tag.get_text(strip=True) if author_tag else None,
                "date": date_tag.get_text(strip=True) if date_tag else None,
            }
        )

    previous_url = None
    for a in soup.select("div.btn-group-paging a.btn.wide"):
        if "上頁" in a.get_text(strip=True) and a.get("href"):
            previous_url = urljoin(BASE_URL, a["href"])
            break

    return articles, previous_url


def redact_pii(text: str) -> str:
    text = PHONE_RE.sub("[PHONE_REDACTED]", text)
    text = EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    text = LINE_RE.sub(r"\1[LINE_ID_REDACTED]", text)
    return text


def parse_article_page(html: str, fallback: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#main-content")
    if main is None:
        return {**fallback, "content": ""}

    meta_values = [m.get_text(strip=True) for m in main.select("span.article-meta-value")]
    author = meta_values[0] if len(meta_values) >= 1 else fallback.get("author")
    board = meta_values[1] if len(meta_values) >= 2 else fallback.get("board")
    title = meta_values[2] if len(meta_values) >= 3 else fallback.get("title")
    posted_time = meta_values[3] if len(meta_values) >= 4 else fallback.get("date")

    # Remove metadata and pushes before extracting main content.
    for tag in main.select("div.article-metaline, div.article-metaline-right, div.push"):
        tag.decompose()

    content = main.get_text("\n", strip=True)
    content = content.split("※ 發信站:")[0]
    content = content.split("--")[0]
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    return {
        **fallback,
        "author": author,
        "board": board,
        "title": title,
        "date": posted_time,
        "content": redact_pii(content),
    }


def extract_keywords(text: str) -> list[str]:
    found = []
    for keyword, pattern in KEYWORD_PATTERNS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(keyword)
    for district in ALL_DISTRICTS:
        if district in text:
            found.append(district)
    return sorted(set(found))


def extract_districts(text: str) -> list[str]:
    return [district for district in ALL_DISTRICTS if district in text]


def extract_prices(text: str) -> list[int]:
    prices: list[int] = []

    def add_token(token: str) -> None:
        value = parse_money_token(token)
        if value is not None and is_plausible_rent(value):
            prices.append(value)

    for pattern in (MONTHLY_RENT_LABEL_RE, GENERIC_MONEY_RE):
        for match in pattern.finditer(text):
            add_token(match.group("num"))

    for pattern in (DOT_THOUSANDS_RE, COMMA_MONEY_RE, PLAIN_MONEY_RE):
        for match in pattern.finditer(text):
            add_token(match.group("num"))

    for match in re.finditer(r"(?P<num>\d+(?:\.\d+)?)\s*[kK]\b", text):
        add_token(match.group("num") + "k")

    for match in re.finditer(r"(?P<num>\d+(?:\.\d+)?)\s*千", text):
        add_token(match.group("num") + "千")

    for match in WAN_MONEY_RE.finditer(text):
        add_token(match.group(0))

    return sorted(set(prices))[:10]


def extract_areas(text: str) -> list[float]:
    areas = []
    for match in AREA_RE.finditer(text):
        area = float(match.group("area"))
        if 1 <= area <= 200:
            areas.append(area)
    return sorted(set(areas))[:10]


def make_short_snippet(text: str, max_len: int = 200) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def article_to_signal(article: dict) -> PTTArticle:
    title = article.get("title") or ""
    content = article.get("content") or ""
    combined = f"{title}\n{content}"
    url = article["url"]
    thread_id = url.rstrip("/").split("/")[-1].replace(".html", "")
    parsed_date = parse_ptt_datetime(article.get("date"))

    return PTTArticle(
        thread_id=thread_id,
        board=article.get("board") or "",
        title=title,
        author=article.get("author"),
        date=article.get("date"),
        posted_at=parsed_date.isoformat(timespec="seconds") if parsed_date else None,
        url=url,
        short_snippet=make_short_snippet(content),
        contains_pricing_question=is_pricing_question(combined),
        keywords=extract_keywords(combined),
        districts=extract_districts(combined),
        extracted_prices_ntd=extract_prices(combined),
        extracted_areas_ping=extract_areas(combined),
    )


def should_keep_signal(
    signal: PTTArticle,
    taipei_only: bool,
    since_date: datetime | None = None,
) -> bool:
    if since_date is not None and not is_recent_enough(signal.date, since_date):
        return False
    if not signal.contains_pricing_question and not signal.extracted_prices_ntd:
        return False
    if taipei_only and not any(d in signal.districts for d in TAIPEI_DISTRICTS + NEW_TAIPEI_DISTRICTS):
        # Titles often use 台北/新北 without district names.
        text = signal.title + " " + signal.short_snippet
        if "台北" not in text and "臺北" not in text and "新北" not in text:
            return False
    return True


def crawl_board(
    session: requests.Session,
    board: str,
    max_pages: int,
    sleep_seconds: float,
    max_articles: int | None,
    check_robots: bool,
    since_date: datetime | None = None,
) -> Iterable[dict]:
    url = f"{BASE_URL}/bbs/{board}/index.html"
    seen_urls: set[str] = set()
    crawled_articles = 0

    for _ in range(max_pages):
        if check_robots and not allowed_by_robots(url):
            raise RuntimeError(f"robots.txt does not allow or cannot confirm access to {url}")
        html = get_html(session, url, sleep_seconds)
        articles, previous_url = parse_index_page(html, board)
        page_has_recent = False

        # Crawl newest first.
        for item in reversed(articles):
            if max_articles is not None and crawled_articles >= max_articles:
                return
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])

            if check_robots and not allowed_by_robots(item["url"]):
                continue
            try:
                article_html = get_html(session, item["url"], sleep_seconds)
                article = parse_article_page(article_html, item)
                if since_date is not None and not is_recent_enough(article.get("date"), since_date):
                    continue
                page_has_recent = True
                yield article
                crawled_articles += 1
            except requests.HTTPError as exc:
                print(f"[WARN] skip {item['url']}: {exc}")
            except Exception as exc:
                print(f"[WARN] skip {item['url']}: {exc}")

        if since_date is not None and not page_has_recent:
            print(f"[INFO] stopping board={board}: no posts newer than {since_date.date()}")
            break
        if not previous_url:
            break
        url = previous_url


def sanitize_raw_article(article: dict) -> dict:
    content = article.pop("content", "") or ""
    return {
        **article,
        "short_snippet": make_short_snippet(content),
    }


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def crawl_forum_signals(
    boards: list[str] | None = None,
    max_pages: int = 2,
    max_articles_per_board: int = 80,
    sleep_seconds: float = 1.0,
    output: str | Path = "data/processed/forum_signals_real.json",
    raw_output: str | Path = "data/raw/ptt_threads.jsonl",
    csv_output: str | Path = "data/processed/forum_signals_real.csv",
    over18: bool = False,
    taipei_only: bool = True,
    skip_robots_check: bool = False,
    since_date: str | None = None,
    since_years: float | None = 2.0,
) -> Path:
    """Programmatic entry point used by Makefile and demand-evidence scripts."""
    boards = boards or DEFAULT_BOARDS
    session = make_session(over18=over18)
    check_robots = not skip_robots_check
    cutoff = resolve_since_date(since_date=since_date, since_years=since_years)
    if cutoff:
        print(f"[INFO] keeping posts on or after {cutoff.date()}")

    raw_articles: list[dict] = []
    signals: list[PTTArticle] = []

    for board in boards:
        print(f"[INFO] crawling board={board}")
        for article in crawl_board(
            session=session,
            board=board,
            max_pages=max_pages,
            sleep_seconds=sleep_seconds,
            max_articles=max_articles_per_board,
            check_robots=check_robots,
            since_date=cutoff,
        ):
            raw_articles.append(article)
            signal = article_to_signal(article)
            if should_keep_signal(signal, taipei_only=taipei_only, since_date=cutoff):
                signals.append(signal)

    raw_path = Path(raw_output)
    out_path = Path(output)
    csv_path = Path(csv_output)

    write_jsonl(raw_path, (sanitize_raw_article(dict(article)) for article in raw_articles))

    signal_rows = [asdict(s) for s in signals]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(signal_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_rows = []
    for row in signal_rows:
        csv_rows.append(
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
                for k, v in row.items()
            }
        )
    write_csv(csv_path, csv_rows)

    print(f"[DONE] raw articles: {len(raw_articles)} -> {raw_path}")
    print(f"[DONE] forum signals: {len(signals)} -> {out_path}")
    print(f"[DONE] csv preview: {csv_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl public PTT rental posts for demand evidence")
    parser.add_argument("--boards", nargs="+", default=DEFAULT_BOARDS)
    parser.add_argument("--max-pages", type=int, default=3, help="Pages per board")
    parser.add_argument("--max-articles-per-board", type=int, default=80)
    parser.add_argument("--sleep", type=float, default=1.0, help="Base delay between requests")
    parser.add_argument("--output", default="data/processed/forum_signals_real.json")
    parser.add_argument("--raw-output", default="data/raw/ptt_threads.jsonl")
    parser.add_argument("--csv-output", default="data/processed/forum_signals_real.csv")
    parser.add_argument("--over18", action="store_true", help="Set PTT over18 cookie when crawling adult-gated boards")
    parser.add_argument("--taipei-only", action="store_true", help="Keep only Taipei/New Taipei related posts")
    parser.add_argument(
        "--since-years",
        type=float,
        default=2.0,
        help="Keep only posts within the last N years (default: 2)",
    )
    parser.add_argument(
        "--since-date",
        default=None,
        help="Keep only posts on/after YYYY-MM-DD (overrides --since-years when set)",
    )
    parser.add_argument(
        "--skip-robots-check",
        action="store_true",
        help="Bypass robots.txt checks (not recommended for submission/demo)",
    )
    args = parser.parse_args()

    crawl_forum_signals(
        boards=args.boards,
        max_pages=args.max_pages,
        max_articles_per_board=args.max_articles_per_board,
        sleep_seconds=args.sleep,
        output=args.output,
        raw_output=args.raw_output,
        csv_output=args.csv_output,
        over18=args.over18,
        taipei_only=args.taipei_only,
        skip_robots_check=args.skip_robots_check,
        since_date=args.since_date,
        since_years=args.since_years,
    )


if __name__ == "__main__":
    main()
