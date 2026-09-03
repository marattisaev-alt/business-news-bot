import os
import re
import json
import time
import hashlib
import html
import statistics
from datetime import datetime, timezone
from urllib.parse import urljoin, quote_plus

import requests
import xml.etree.ElementTree as ET


# =========================================================
# МРК BUSINESS NEWS BOT 6.0
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")

MAX_POSTS_PER_RUN = 2
MIN_SCORE = 9
MAX_CANDIDATES = 70
MAX_NEWS_AGE_HOURS = 48
MAX_IMAGE_SIZE = 9 * 1024 * 1024

POSTED_FILE = "posted.json"
USED_IMAGES_FILE = "used_images.json"

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}


# =========================================================
# RSS
# =========================================================

RSS_FEEDS = [
    (
        "Reuters",
        "https://news.google.com/rss/search?q="
        "business+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "USA",
        "https://news.google.com/rss/search?q="
        "US+business+economy+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Russia",
        "https://news.google.com/rss/search?q="
        "Russia+business+economy+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Markets",
        "https://news.google.com/rss/search?q="
        "stock+market+finance+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Economy",
        "https://news.google.com/rss/search?q="
        "economy+inflation+interest+rates+when:2d"
        "&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Technology",
        "https://news.google.com/rss/search?q="
        "technology+AI+chips+business+when:2d"
        "&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Business",
        "https://news.google.com/rss/search?q="
        "companies+corporate+business+when:2d"
        "&hl=en-US&gl=US&ceid=US:en"
    ),
]


# =========================================================
# КЛЮЧЕВЫЕ СЛОВА
# =========================================================

CRITICAL_WORDS = [
    "bankruptcy", "bankrupt", "collapse", "crisis",
    "default", "war", "emergency", "fraud",
    "investigation", "lawsuit", "sanctions",
    "sanction", "tariff", "tariffs",
    "ban", "banned", "recall"
]

MONEY_WORDS = [
    "million", "billion", "trillion",
    "revenue", "profit", "loss",
    "earnings", "valuation",
    "investment", "funding",
    "deal", "acquisition",
    "merger", "debt"
]

FINANCE_WORDS = [
    "bank", "banks", "banking",
    "fed", "federal reserve",
    "ecb", "central bank",
    "interest rate", "interest rates",
    "inflation", "deflation",
    "currency", "dollar", "euro",
    "bond", "bonds", "credit",
    "loan", "finance", "financial"
]

TECH_WORDS = [
    "ai", "artificial intelligence",
    "technology", "software",
    "chip", "chips",
    "semiconductor", "semiconductors",
    "data center", "data centre",
    "cloud", "robot", "robotics",
    "automation",
    "nvidia", "microsoft",
    "google", "openai",
    "apple", "meta",
    "amazon", "intel", "amd"
]

MARKET_WORDS = [
    "stock", "stocks",
    "stock market",
    "shares", "share price",
    "trading", "trader",
    "exchange", "wall street",
    "nasdaq", "dow jones",
    "s&p", "rally",
    "surge", "jump",
    "gain", "rise",
    "drop", "fall",
    "fell", "plunge",
    "decline", "selloff",
    "sell-off",
    "record high",
    "record low"
]

MACRO_WORDS = [
    "economy", "economic",
    "inflation", "gdp",
    "employment", "jobs",
    "unemployment",
    "recession", "growth",
    "trade", "tariff",
    "rate cut", "rate hike"
]

USA_WORDS = [
    "usa", "u.s.",
    "united states",
    "washington", "new york",
    "american", "america",
    "california", "texas",
    "wall street"
]

RUSSIA_WORDS = [
    "russia", "russian",
    "moscow",
    "gazprom", "rosneft",
    "sberbank", "yandex",
    "lukoil", "novatek",
    "vtb", "ozon",
    "wildberries"
]

LOW_VALUE_WORDS = [
    "horoscope", "celebrity",
    "movie", "football",
    "soccer", "recipe",
    "lottery", "entertainment"
]

CLICKBAIT_WORDS = [
    "you won't believe",
    "shocking",
    "unbelievable",
    "secret",
    "what happens next",
    "must see",
    "click here"
]


# =========================================================
# КОМПАНИИ И ТИКЕРЫ
# =========================================================

COMPANIES = {
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "openai": None,
    "intel": "INTC",
    "amd": "AMD",
    "ford": "F",
    "toyota": "TM",
    "walmart": "WMT",
    "netflix": "NFLX",
    "uber": "UBER",
    "coinbase": "COIN",
    "paypal": "PYPL",
    "bank of america": "BAC",
    "jpmorgan": "JPM",
    "goldman sachs": "GS",
    "sberbank": None,
    "gazprom": None,
    "rosneft": None,
    "lukoil": None,
    "yandex": None
}


# =========================================================
# ИЗОБРАЖЕНИЯ
# =========================================================

IMAGE_THEMES = {
    "technology": [
        "ai", "artificial intelligence",
        "chip", "chips", "semiconductor",
        "nvidia", "microsoft", "google",
        "openai", "apple", "meta",
        "data center", "software",
        "robot", "robotics"
    ],

    "auto": [
        "tesla", "car", "cars",
        "automotive", "vehicle",
        "electric vehicle", "ev",
        "ford", "toyota",
        "volkswagen", "bmw",
        "mercedes"
    ],

    "energy": [
        "oil", "gas", "energy",
        "opec", "crude",
        "refinery", "pipeline",
        "lng", "petroleum",
        "electricity"
    ],

    "markets": [
        "stock", "stocks",
        "stock market",
        "trading", "trader",
        "exchange", "wall street",
        "nasdaq", "dow jones",
        "s&p", "shares"
    ],

    "finance": [
        "bank", "banks",
        "banking", "fed",
        "federal reserve",
        "ecb", "central bank",
        "dollar", "euro",
        "currency", "finance"
    ],

    "russia": [
        "russia", "russian",
        "moscow", "gazprom",
        "rosneft", "sberbank",
        "yandex", "lukoil",
        "novatek"
    ]
}

GENERIC_IMAGE_WORDS = [
    "logo", "icon", "avatar",
    "favicon", "sprite",
    "placeholder", "default",
    "no-image", "no_image",
    "thumbnail", "thumb",
    "banner", "advertisement",
    "pixel"
]


# =========================================================
# UTILS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^\w\s\-.]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def escape_html(text):
    return html.escape(text or "", quote=False)


def shorten(text, limit):
    text = clean_text(text)

    if len(text) <= limit:
        return text

    return text[:limit - 3].rstrip() + "..."


# =========================================================
# FILE HISTORY
# =========================================================

def load_json_file(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    except Exception:
        return default


def save_json_file(filename, data, limit=2000):
    if isinstance(data, list):
        data = data[-limit:]

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def load_posted():
    data = load_json_file(
        POSTED_FILE,
        []
    )

    return data if isinstance(data, list) else []


def load_used_images():
    data = load_json_file(
        USED_IMAGES_FILE,
        []
    )

    return data if isinstance(data, list) else []


# =========================================================
# DATE
# =========================================================

def parse_date(value):
    if not value:
        return None

    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(
                value.strip(),
                fmt
            )

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt

        except Exception:
            pass

    return None


def age_hours(dt):
    if not dt:
        return 0

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return max(
        0,
        (
            datetime.now(timezone.utc) - dt
        ).total_seconds() / 3600
    )


# =========================================================
# RSS
# =========================================================

def fetch(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=25
        )

        r.raise_for_status()

        return r.text

    except Exception as e:
        print("FETCH ERROR:", e)
        return ""


def parse_rss(xml_text, feed_name):
    articles = []

    if not xml_text:
        return articles

    try:
        root = ET.fromstring(xml_text)

    except Exception as e:
        print("XML ERROR:", e)
        return articles

    for item in root.findall(".//item"):

        title = clean_text(
            item.findtext("title", "")
        )

        link = clean_text(
            item.findtext("link", "")
        )

        description = clean_text(
            item.findtext(
                "description",
                ""
            )
        )

        pub_date = clean_text(
            item.findtext(
                "pubDate",
                ""
            )
        )

        source = clean_text(
            item.findtext(
                "{http://search.yahoo.com/mrss/}source",
                ""
            )
        )

        if not source:
            source = feed_name

        if not title or not link:
            continue

        articles.append({
            "title": title,
            "description": description,
            "url": link,
            "source": source,
            "feed": feed_name,
            "date": parse_date(pub_date)
        })

    return articles


# =========================================================
# KEYWORDS
# =========================================================

def contains_any(text, words):
    text = normalize(text)

    return any(
        word in text
        for word in words
    )


def extract_numbers(text):
    text = clean_text(text)

    patterns = [
        r"\$[\d,.]+\s*(?:million|billion|trillion)?",
        r"€[\d,.]+\s*(?:million|billion|trillion)?",
        r"£[\d,.]+\s*(?:million|billion|trillion)?",
        r"\b\d+(?:\.\d+)?%\b",
        r"\b\d+(?:\.\d+)?\s*(?:million|billion|trillion)\b"
    ]

    found = []

    for pattern in patterns:
        for value in re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        ):
            value = value.strip()

            if value not in found:
                found.append(value)

    return found[:6]


def detect_companies(article):
    text = normalize(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    found = []

    for company in COMPANIES:

        if company in text:
            found.append(company)

    return found[:5]


# =========================================================
# CATEGORY
# =========================================================

def detect_category(article):
    text = normalize(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    scores = {
        "Технологии": 0,
        "Рынки": 0,
        "Финансы": 0,
        "Энергетика": 0,
        "Россия": 0,
        "США": 0,
        "Экономика": 0,
        "Бизнес": 0
    }

    for word in TECH_WORDS:
        if word in text:
            scores["Технологии"] += 3

    for word in MARKET_WORDS:
        if word in text:
            scores["Рынки"] += 3

    for word in FINANCE_WORDS:
        if word in text:
            scores["Финансы"] += 3

    for word in USA_WORDS:
        if word in text:
            scores["США"] += 2

    for word in RUSSIA_WORDS:
        if word in text:
            scores["Россия"] += 3

    for word in MACRO_WORDS:
        if word in text:
            scores["Экономика"] += 3

    if contains_any(
        text,
        [
            "oil", "gas", "energy",
            "opec", "crude",
            "refinery", "pipeline"
        ]
    ):
        scores["Энергетика"] += 6

    category = max(
        scores,
        key=scores.get
    )

    if scores[category] == 0:
        return "Бизнес"

    return category


# =========================================================
# SOURCE QUALITY
# =========================================================

SOURCE_WEIGHTS = {
    "reuters": 10,
    "bloomberg": 10,
    "financial times": 9,
    "wall street journal": 9,
    "cnbc": 8,
    "associated press": 8,
    "ap news": 8,
    "bbc": 7,
    "cnn": 6,
    "forbes": 7,
    "marketwatch": 7,
    "yahoo finance": 7,
    "business insider": 6,
    "tass": 6,
    "interfax": 6,
    "ria": 5
}


def source_score(source):
    source = normalize(source)

    for name, score in SOURCE_WEIGHTS.items():

        if name in source:
            return score

    return 3


# =========================================================
# NEWS IMPORTANCE
# =========================================================

def clickbait_penalty(text):
    penalty = 0

    for word in CLICKBAIT_WORDS:
        if word in text:
            penalty += 4

    if text.count("!") >= 3:
        penalty += 4

    return penalty


def calculate_score(article):
    title = normalize(
        article.get("title", "")
    )

    description = normalize(
        article.get("description", "")
    )

    text = title + " " + description

    score = 0

    # Свежесть
    age = age_hours(
        article.get("date")
    )

    if age <= 2:
        score += 8
    elif age <= 6:
        score += 6
    elif age <= 12:
        score += 5
    elif age <= 24:
        score += 4
    elif age <= 48:
        score += 2

    # Источник
    score += source_score(
        article.get("source", "")
    )

    # Деньги
    if contains_any(text, MONEY_WORDS):
        score += 4

    # Финансы
    if contains_any(text, FINANCE_WORDS):
        score += 4

    # Рынки
    if contains_any(text, MARKET_WORDS):
        score += 4

    # Технологии
    if contains_any(text, TECH_WORDS):
        score += 3

    # Макро
    if contains_any(text, MACRO_WORDS):
        score += 3

    # Крупные события
    for word in CRITICAL_WORDS:
        if word in text:
            score += 5

    # Компании
    companies = detect_companies(article)

    score += min(
        len(companies) * 2,
        8
    )

    # Крупные суммы
    numbers = extract_numbers(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    if numbers:
        score += 3

    # Кликбейт
    score -= clickbait_penalty(text)

    # Низкокачественный контент
    for word in LOW_VALUE_WORDS:
        if word in text:
            score -= 10

    return score


# =========================================================
# SIMILARITY
# =========================================================

def important_words(text):
    words = re.findall(
        r"\b[a-zа-яё0-9][a-zа-яё0-9\-]{3,}\b",
        normalize(text),
        flags=re.IGNORECASE
    )

    stop = {
        "this", "that", "with",
        "from", "have", "will",
        "about", "after", "before",
        "into", "their", "they",
        "them", "were", "been",
        "said", "says", "which",
        "when", "where", "what",
        "как", "это", "для",
        "что", "при", "после",
        "перед", "также", "будет",
        "был", "была", "были"
    }

    result = []

    for word in words:

        if word in stop:
            continue

        if word not in result:
            result.append(word)

    return result[:35]


def similarity(a, b):
    a_words = set(
        important_words(
            a.get("title", "")
        )
    )

    b_words = set(
        important_words(
            b.get("title", "")
        )
    )

    if not a_words or not b_words:
        return 0

    return len(
        a_words & b_words
    ) / len(
        a_words | b_words
    )


def remove_similar_news(articles):
    result = []

    for article in articles:

        duplicate = False

        for existing in result:

            if similarity(
                article,
                existing
            ) >= 0.52:

                duplicate = True
                break

        if not duplicate:
            result.append(article)

    return result


# =========================================================
# EDITORIAL ENGINE
# =========================================================

def editorial_title(article):
    title = clean_text(
        article.get("title", "")
    )

    # Убираем типичный мусор Google News
    title = re.sub(
        r"\s*-\s*[^-]{2,40}$",
        "",
        title
    ).strip()

    title = shorten(
        title,
        170
    )

    lower = normalize(title)

    urgent = contains_any(
        lower,
        CRITICAL_WORDS
    )

    market = contains_any(
        lower,
        MARKET_WORDS
    )

    numbers = extract_numbers(title)

    prefix = ""

    if urgent:
        prefix = "🚨 "
    elif market:
        prefix = "📈 "

    # Не добавляем emoji дважды
    if title.startswith(
        ("🔥", "🚨", "📈", "💰", "⚡")
    ):
        prefix = ""

    # Для важных финансовых новостей
    if numbers and not prefix:
        prefix = "💰 "

    return prefix + title


def generate_summary(article):
    description = clean_text(
        article.get("description", "")
    )

    title = clean_text(
        article.get("title", "")
    )

    if description:
        summary = description
    else:
        summary = title

    summary = re.sub(
        r"\s*-\s*[^-]{2,40}$",
        "",
        summary
    )

    return shorten(
        summary,
        430
    )


def generate_analysis(article):
    category = detect_category(article)

    text = normalize(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    companies = detect_companies(
        article
    )

    numbers = extract_numbers(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    if category == "Рынки":
        reason = (
            "событие может повлиять на настроения "
            "инвесторов и движение активов"
        )

    elif category == "Финансы":
        reason = (
            "новость связана с финансовыми условиями "
            "и может иметь последствия для рынка"
        )

    elif category == "Технологии":
        reason = (
            "событие важно для технологического сектора "
            "и крупных игроков рынка"
        )

    elif category == "Энергетика":
        reason = (
            "изменения в энергетическом секторе "
            "могут отражаться на стоимости сырья и компаний"
        )

    elif category == "Экономика":
        reason = (
            "изменение экономических условий "
            "может повлиять на бизнес и потребителей"
        )

    elif category == "Россия":
        reason = (
            "событие имеет значение для российского "
            "бизнеса или экономики"
        )

    elif category == "США":
        reason = (
            "решение или событие может отразиться "
            "на американском рынке"
        )

    else:
        reason = (
            "событие представляет интерес "
            "для деловой аудитории"
        )

    if companies:
        reason += (
            f". В новости фигурирует "
            f"{companies[0].title()}"
        )

    if numbers:
        reason += (
            f". Ключевой показатель: {numbers[0]}"
        )

    return reason + "."


def hashtags(article):
    category = detect_category(article)

    mapping = {
        "Технологии":
            "#Технологии #AI #Бизнес",
        "Рынки":
            "#Рынки #Акции #Инвестиции",
        "Финансы":
            "#Финансы #Деньги #Экономика",
        "Энергетика":
            "#Энергетика #Нефть #Газ",
        "Россия":
            "#Россия #Бизнес #Экономика",
        "США":
            "#США #Бизнес #Экономика",
        "Экономика":
            "#Экономика #Бизнес #Рынки",
        "Бизнес":
            "#Бизнес #Компании #Экономика"
    }

    result = mapping.get(
        category,
        "#Бизнес #Экономика"
    )

    companies = detect_companies(
        article
    )

    if companies:

        company_tag = re.sub(
            r"[^A-Za-zА-Яа-я0-9]",
            "",
            companies[0]
        )

        if company_tag:
            result += " #" + company_tag

    return result


# =========================================================
# MARKET DATA
# =========================================================

def yahoo_quote(ticker):
    try:

        url = (
            "https://query1.finance.yahoo.com/"
            "v8/finance/chart/"
            + quote_plus(ticker)
        )

        params = {
            "range": "1d",
            "interval": "1m"
        }

        r = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=12
        )

        r.raise_for_status()

        data = r.json()

        result = data.get(
            "chart",
            {}
        ).get(
            "result"
        )

        if not result:
            return None

        meta = result[0].get(
            "meta",
            {}
        )

        price = meta.get(
            "regularMarketPrice"
        )

        previous = meta.get(
            "chartPreviousClose"
        )

        if price is None or previous is None:
            return None

        change = price - previous

        percent = (
            change / previous * 100
            if previous
            else 0
        )

        return {
            "ticker": ticker,
            "price": price,
            "change": change,
            "percent": percent
        }

    except Exception as e:

        print(
            "MARKET ERROR",
            ticker,
            e
        )

        return None


def market_snapshot(article):
    companies = detect_companies(
        article
    )

    result = []

    for company in companies:

        ticker = COMPANIES.get(
            company
        )

        if not ticker:
            continue

        quote = yahoo_quote(
            ticker
        )

        if quote:
            quote["company"] = company
            result.append(quote)

    return result[:3]


def global_market_snapshot():
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Brent": "BZ=F",
        "Bitcoin": "BTC-USD"
    }

    result = []

    for name, ticker in tickers.items():

        quote = yahoo_quote(
            ticker
        )

        if quote:

            quote["name"] = name
            result.append(quote)

    return result


# =========================================================
# CURRENCY
# =========================================================

def currency_rate(pair):
    try:

        url = (
            "https://query1.finance.yahoo.com/"
            "v8/finance/chart/"
            + quote_plus(pair)
        )

        params = {
            "range": "1d",
            "interval": "1d"
        }

        r = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=10
        )

        r.raise_for_status()

        data = r.json()

        result = data.get(
            "chart",
            {}
        ).get(
            "result"
        )

        if not result:
            return None

        meta = result[0].get(
            "meta",
            {}
        )

        return meta.get(
            "regularMarketPrice"
        )

    except Exception:
        return None


# =========================================================
# IMAGE SEARCH
# =========================================================

def add_image(
    candidates,
    url,
    source_type,
    alt="",
    title="",
    context=""
):
    if not url:
        return

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(
        ("http://", "https://")
    ):
        return

    candidates.append({
        "url": url,
        "source_type": source_type,
        "alt": clean_text(alt),
        "title": clean_text(title),
        "context": clean_text(context)
    })


def extract_srcset(value):
    result = []

    for item in value.split(","):

        parts = item.strip().split()

        if parts:
            result.append(
                parts[0]
            )

    return result


def extract_images(page_html, page_url):
    candidates = []

    patterns = [
        (
            r'<meta[^>]+property=["\']og:image'
            r'["\'][^>]+content=["\']([^"\']+)',
            "og"
        ),
        (
            r'<meta[^>]+content=["\']([^"\']+)'
            r'["\'][^>]+property=["\']og:image',
            "og"
        ),
        (
            r'<meta[^>]+name=["\']twitter:image'
            r'["\'][^>]+content=["\']([^"\']+)',
            "twitter"
        ),
        (
            r'<meta[^>]+content=["\']([^"\']+)'
            r'["\'][^>]+name=["\']twitter:image',
            "twitter"
        ),
        (
            r'<link[^>]+rel=["\']image_src'
            r'["\'][^>]+href=["\']([^"\']+)',
            "image_src"
        )
    ]

    for pattern, source in patterns:

        for match in re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        ):

            add_image(
                candidates,
                urljoin(
                    page_url,
                    match
                ),
                source
            )

    # JSON-LD
    blocks = re.findall(
        r'<script[^>]+type=["\']'
        r'application/ld\+json["\'][^>]*>'
        r'(.*?)</script>',
        page_html,
        flags=re.IGNORECASE |
        re.DOTALL
    )

    for block in blocks:

        try:

            data = json.loads(
                html.unescape(
                    block.strip()
                )
            )

            objects = (
                data
                if isinstance(data, list)
                else [data]
            )

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                image = obj.get(
                    "image"
                )

                if isinstance(
                    image,
                    str
                ):
                    add_image(
                        candidates,
                        urljoin(
                            page_url,
                            image
                        ),
                        "jsonld"
                    )

                elif isinstance(
                    image,
                    list
                ):

                    for img in image[:5]:

                        if isinstance(
                            img,
                            str
                        ):
                            add_image(
                                candidates,
                                urljoin(
                                    page_url,
                                    img
                                ),
                                "jsonld"
                            )

                        elif isinstance(
                            img,
                            dict
                        ):

                            img_url = img.get(
                                "url"
                            )

                            if img_url:
                                add_image(
                                    candidates,
                                    urljoin(
                                        page_url,
                                        img_url
                                    ),
                                    "jsonld"
                                )

        except Exception:
            continue

    # IMG
    for match in re.finditer(
        r"<img\b([^>]+)>",
        page_html,
        flags=re.IGNORECASE |
        re.DOTALL
    ):

        attrs = match.group(1)

        src = ""

        for attr in [
            "src",
            "data-src",
            "data-lazy-src"
        ]:

            found = re.search(
                rf'\b{attr}=["\']([^"\']+)',
                attrs,
                flags=re.IGNORECASE
            )

            if found:
                src = found.group(1)
                break

        if not src:
            continue

        alt_match = re.search(
            r'\balt=["\']([^"\']*)',
            attrs,
            flags=re.IGNORECASE
        )

        title_match = re.search(
            r'\btitle=["\']([^"\']*)',
            attrs,
            flags=re.IGNORECASE
        )

        alt = (
            alt_match.group(1)
            if alt_match
            else ""
        )

        title = (
            title_match.group(1)
            if title_match
            else ""
        )

        context = clean_text(
            page_html[
                max(0, match.start() - 600):
                min(
                    len(page_html),
                    match.end() + 600
                )
            ]
        )

        add_image(
            candidates,
            urljoin(
                page_url,
                src
            ),
            "img",
            alt,
            title,
            context
        )

        srcset = re.search(
            r'\bsrcset=["\']([^"\']+)',
            attrs,
            flags=re.IGNORECASE
        )

        if srcset:

            for srcset_url in extract_srcset(
                srcset.group(1)
            ):

                add_image(
                    candidates,
                    urljoin(
                        page_url,
                        srcset_url
                    ),
                    "srcset",
                    alt,
                    title,
                    context
                )

    # Дедупликация
    unique = []
    seen = set()

    for item in candidates:

        if item["url"] in seen:
            continue

        seen.add(
            item["url"]
        )

        unique.append(item)

    return unique


def image_score(article, candidate):
    article_text = normalize(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    metadata = normalize(
        candidate.get("alt", "") +
        " " +
        candidate.get("title", "") +
        " " +
        candidate.get("context", "") +
        " " +
        candidate.get("url", "")
    )

    category = detect_category(
        article
    )

    theme_map = {
        "Технологии": "technology",
        "Рынки": "markets",
        "Финансы": "finance",
        "Энергетика": "energy",
        "Россия": "russia"
    }

    score = {
        "og": 7,
        "twitter": 6,
        "jsonld": 6,
        "image_src": 5,
        "srcset": 3,
        "img": 2
    }.get(
        candidate.get("source_type"),
        1
    )

    theme = theme_map.get(
        category
    )

    if theme:

        for word in IMAGE_THEMES.get(
            theme,
            []
        ):

            if word in metadata:
                score += 6

    for word in important_words(
        article.get("title", "") +
        " " +
        article.get("description", "")
    ):

        if len(word) >= 5 and word in metadata:
            score += 2

    for company in detect_companies(
        article
    ):

        if company in metadata:
            score += 12

    for word in GENERIC_IMAGE_WORDS:

        if word in metadata:
            score -= 10

    if "logo" in metadata:
        score -= 15

    if "placeholder" in metadata:
        score -= 15

    return score


def get_best_image(article, used_images):
    url = article.get("url")

    if not url:
        return None

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        r.raise_for_status()

        candidates = extract_images(
            r.text,
            r.url
        )

    except Exception as e:

        print(
            "IMAGE PAGE ERROR:",
            e
        )

        return None

    ranked = []

    for candidate in candidates:

        candidate["score"] = image_score(
            article,
            candidate
        )

        ranked.append(candidate)

    ranked.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    print(
        "IMAGE CANDIDATES:",
        len(ranked)
    )

    for candidate in ranked[:15]:

        print(
            "IMAGE:",
            candidate["score"],
            candidate["source_type"],
            candidate["url"][:120]
        )

        try:

            response = requests.get(
                candidate["url"],
                headers=HEADERS,
                timeout=25,
                stream=True
            )

            response.raise_for_status()

            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
                .lower()
                .split(";")[0]
            )

            if content_type not in {
                "image/jpeg",
                "image/jpg",
                "image/png"
            }:
                continue

            chunks = []
            total = 0

            for chunk in response.iter_content(
                chunk_size=64 * 1024
            ):

                if not chunk:
                    continue

                total += len(chunk)

                if total > MAX_IMAGE_SIZE:
                    break

                chunks.append(chunk)

            content = b"".join(
                chunks
            )

            if len(content) < 5000:
                continue

            image_hash = hashlib.sha256(
                content
            ).hexdigest()

            if image_hash in used_images:
                continue

            return {
                "content": content,
                "hash": image_hash,
                "score": candidate["score"]
            }

        except Exception:
            continue

    return None


# =========================================================
# TELEGRAM
# =========================================================

def tg_url(method):
    return (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/{method}"
    )


def send_message(
    text,
    keyboard
):
    try:

        r = requests.post(
            tg_url("sendMessage"),
            data={
                "chat_id": CHANNEL,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": json.dumps(
                    keyboard
                )
            },
            timeout=30
        )

        print(
            "TELEGRAM MESSAGE:",
            r.status_code,
            r.text[:500]
        )

        return r.ok

    except Exception as e:

        print(
            "TELEGRAM ERROR:",
            e
        )

        return False


def send_photo(
    image,
    caption,
    keyboard
):
    try:

        r = requests.post(
            tg_url("sendPhoto"),
            data={
                "chat_id": CHANNEL,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(
                    keyboard
                )
            },
            files={
                "photo": (
                    "news.jpg",
                    image,
                    "image/jpeg"
                )
            },
            timeout=60
        )

        print(
            "TELEGRAM PHOTO:",
            r.status_code,
            r.text[:500]
        )

        return r.ok

    except Exception as e:

        print(
            "PHOTO ERROR:",
            e
        )

        return False


# =========================================================
# POST BUILDER
# =========================================================

def build_post(article):
    title = editorial_title(
        article
    )

    summary = generate_summary(
        article
    )

    category = detect_category(
        article
    )

    numbers = extract_numbers(
        article.get("title", "") +
        " " +
        article.get("description", "")
    )

    analysis = generate_analysis(
        article
    )

    company_data = market_snapshot(
        article
    )

    lines = []

    lines.append(
        f"<b>{escape_html(title)}</b>"
    )

    if summary:
        lines.append(
            escape_html(summary)
        )

    # Ключевые показатели
    if numbers:

        lines.append(
            "<b>💰 Ключевые показатели:</b>\n"
            +
            "\n".join(
                f"• {escape_html(x)}"
                for x in numbers[:4]
            )
        )

    # Компания / рынок
    if company_data:

        market_lines = []

        for item in company_data:

            sign = (
                "📈"
                if item["percent"] >= 0
                else "📉"
            )

            market_lines.append(
                f"{sign} "
                f"<b>{escape_html(item['company'].title())}</b>: "
                f"{item['price']:.2f} "
                f"({item['percent']:+.2f}%)"
            )

        lines.append(
            "<b>📊 Рынок:</b>\n" +
            "\n".join(market_lines)
        )

    lines.append(
        f"<b>💡 Почему это важно:</b>\n"
        f"{escape_html(analysis)}"
    )

    lines.append(
        f"<b>Категория:</b> "
        f"#{escape_html(category)}"
    )

    lines.append(
        f"<i>Источник: "
        f"{escape_html(article.get('source', 'Источник'))}"
        f"</i>"
    )

    lines.append(
        hashtags(article)
    )

    return "\n\n".join(lines)


def keyboard(article):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📰 Читать источник",
                    "url": article.get(
                        "url",
                        ""
                    )
                }
            ]
        ]
    }


# =========================================================
# QUALITY CONTROL
# =========================================================

def quality_check(article):
    title = clean_text(
        article.get("title", "")
    )

    description = clean_text(
        article.get("description", "")
    )

    if len(title) < 15:
        return False, "short title"

    if len(title) > 300:
        return False, "title too long"

    if not article.get("url"):
        return False, "no url"

    if age_hours(
        article.get("date")
    ) > MAX_NEWS_AGE_HOURS:
        return False, "too old"

    text = normalize(
        title + " " + description
    )

    if all(
        word in text
        for word in LOW_VALUE_WORDS[:2]
    ):
        return False, "low value"

    if clickbait_penalty(text) >= 8:
        return False, "clickbait"

    return True, "OK"


# =========================================================
# NEWS SELECTION
# =========================================================

def select_articles(
    articles,
    posted
):
    candidates = []

    seen_urls = set()

    for article in articles:

        url = article.get(
            "url"
        )

        if not url:
            continue

        if url in posted:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        if age_hours(
            article.get("date")
        ) > MAX_NEWS_AGE_HOURS:
            continue

        ok, reason = quality_check(
            article
        )

        if not ok:
            print(
                "REJECT:",
                reason,
                article.get("title")
            )
            continue

        score = calculate_score(
            article
        )

        if score < MIN_SCORE:
            continue

        article["score"] = score
        article["category"] = detect_category(
            article
        )

        candidates.append(
            article
        )

    candidates.sort(
        key=lambda x: (
            x.get("score", 0),
            -age_hours(
                x.get("date")
            )
        ),
        reverse=True
    )

    return remove_similar_news(
        candidates
    )[:MAX_CANDIDATES]


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing"
        )

    print("=" * 70)
    print(
        "МРК BUSINESS NEWS BOT 6.0"
    )
    print("=" * 70)

    posted = load_posted()
    used_images = load_used_images()

    print(
        "Posted:",
        len(posted)
    )

    print(
        "Used images:",
        len(used_images)
    )

    # -----------------------------------------------------
    # RSS
    # -----------------------------------------------------

    all_articles = []

    for name, url in RSS_FEEDS:

        print(
            "\nRSS:",
            name
        )

        xml = fetch(url)

        parsed = parse_rss(
            xml,
            name
        )

        print(
            "FOUND:",
            len(parsed)
        )

        all_articles.extend(
            parsed
        )

    print(
        "\nTOTAL:",
        len(all_articles)
    )

    # -----------------------------------------------------
    # Отбор
    # -----------------------------------------------------

    selected = select_articles(
        all_articles,
        posted
    )

    print(
        "SELECTED:",
        len(selected)
    )

    # -----------------------------------------------------
    # Публикация
    # -----------------------------------------------------

    published = 0

    for article in selected:

        if published >= MAX_POSTS_PER_RUN:
            break

        print("\n" + "=" * 70)

        print(
            "TITLE:",
            article.get("title")
        )

        print(
            "SCORE:",
            article.get("score")
        )

        print(
            "CATEGORY:",
            article.get("category")
        )

        # -------------------------------------------------
        # Формируем пост
        # -------------------------------------------------

        post = build_post(
            article
        )

        # Telegram caption ограничен,
        # поэтому если пост слишком большой,
        # используем более короткую версию.
        if len(post) > 1000:

            post = (
                f"<b>{escape_html(editorial_title(article))}</b>\n\n"
                f"{escape_html(shorten(generate_summary(article), 350))}\n\n"
                f"<b>💡 Почему это важно:</b>\n"
                f"{escape_html(shorten(generate_analysis(article), 350))}\n\n"
                f"{hashtags(article)}"
            )

        kb = keyboard(
            article
        )

        # -------------------------------------------------
        # Фото
        # -------------------------------------------------

        image = get_best_image(
            article,
            used_images
        )

        success = False

        if image:

            print(
                "IMAGE SCORE:",
                image["score"]
            )

            success = send_photo(
                image["content"],
                post,
                kb
            )

            if success:

                used_images.append(
                    image["hash"]
                )

                save_json_file(
                    USED_IMAGES_FILE,
                    used_images,
                    2000
                )

        # -------------------------------------------------
        # Fallback
        # -------------------------------------------------

        if not success:

            print(
                "TEXT FALLBACK"
            )

            success = send_message(
                post,
                kb
            )

        # -------------------------------------------------
        # История
        # -------------------------------------------------

        if success:

            url = article.get(
                "url"
            )

            if url not in posted:
                posted.append(url)

            save_json_file(
                POSTED_FILE,
                posted,
                1000
            )

            published += 1

            print(
                "PUBLISHED:",
                published
            )

            time.sleep(4)

        else:

            print(
                "FAILED:",
                article.get("url")
            )

    print("\n" + "=" * 70)

    print(
        "DONE"
    )

    print(
        "Published:",
        published
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
