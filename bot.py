import os
import re
import json
import time
import hashlib
import html
import statistics
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
import xml.etree.ElementTree as ET


# =========================================================
# НАСТРОЙКИ
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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
    )
}


# =========================================================
# RSS-ИСТОЧНИКИ
# =========================================================

RSS_FEEDS = [
    (
        "Reuters",
        "https://news.google.com/rss/search?q="
        + quote_plus("business when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "USA Business",
        "https://news.google.com/rss/search?q="
        + quote_plus("USA business economy when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Russia Business",
        "https://news.google.com/rss/search?q="
        + quote_plus("Russia business economy when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Markets",
        "https://news.google.com/rss/search?q="
        + quote_plus("stock market finance markets when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Economy",
        "https://news.google.com/rss/search?q="
        + quote_plus("inflation interest rates economy when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Technology",
        "https://news.google.com/rss/search?q="
        + quote_plus("AI chips technology business when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "Companies",
        "https://news.google.com/rss/search?q="
        + quote_plus("companies corporate business when:2d")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
]


# =========================================================
# КЛЮЧЕВЫЕ СЛОВА
# =========================================================

CRITICAL_WORDS = [
    "bankruptcy",
    "collapse",
    "crisis",
    "default",
    "war",
    "emergency",
    "fraud",
    "investigation",
    "lawsuit",
    "sanctions",
    "tariff",
    "ban",
    "recall",
]

MONEY_WORDS = [
    "million",
    "billion",
    "trillion",
    "revenue",
    "profit",
    "loss",
    "earnings",
    "valuation",
    "investment",
    "funding",
    "deal",
    "acquisition",
    "merger",
    "debt",
]

FINANCE_WORDS = [
    "bank",
    "fed",
    "ecb",
    "central bank",
    "rates",
    "inflation",
    "currency",
    "dollar",
    "euro",
    "bond",
    "credit",
    "loan",
    "finance",
]

TECH_WORDS = [
    "ai",
    "artificial intelligence",
    "technology",
    "software",
    "chip",
    "semiconductor",
    "data center",
    "cloud",
    "robot",
    "nvidia",
    "microsoft",
    "google",
    "openai",
    "apple",
    "meta",
    "amazon",
    "intel",
    "amd",
]

MARKET_WORDS = [
    "stock",
    "stocks",
    "shares",
    "trading",
    "exchange",
    "wall street",
    "nasdaq",
    "dow jones",
    "s&p",
    "rally",
    "surge",
    "jump",
    "gain",
    "rise",
    "drop",
    "fall",
    "plunge",
    "decline",
    "selloff",
    "record high",
    "record low",
]

MACRO_WORDS = [
    "economy",
    "inflation",
    "gdp",
    "employment",
    "unemployment",
    "recession",
    "growth",
    "trade",
    "tariff",
    "rate cut",
    "rate hike",
]

USA_WORDS = [
    "usa",
    "united states",
    "america",
    "american",
    "washington",
    "new york",
    "california",
]

RUSSIA_WORDS = [
    "russia",
    "russian",
    "moscow",
    "rubles",
    "ruble",
    "sberbank",
    "gazprom",
    "rosneft",
    "lukoil",
    "yandex",
]

LOW_VALUE_WORDS = [
    "celebrity",
    "entertainment",
    "movie",
    "music",
    "sports",
    "football",
    "soccer",
    "match",
    "game",
]

CLICKBAIT_WORDS = [
    "you won't believe",
    "shocking",
    "unbelievable",
    "this is why",
    "what happens next",
    "must see",
    "secret",
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
    "yandex": None,
}


# =========================================================
# ИЗОБРАЖЕНИЯ
# =========================================================

IMAGE_THEMES = {
    "markets": [
        "stock",
        "stocks",
        "market",
        "exchange",
        "trading",
        "wall street",
        "nasdaq",
        "dow",
        "shares",
    ],
    "technology": [
        "ai",
        "artificial intelligence",
        "technology",
        "chip",
        "semiconductor",
        "computer",
        "robot",
        "data center",
        "cloud",
    ],
    "finance": [
        "bank",
        "finance",
        "money",
        "dollar",
        "euro",
        "credit",
        "loan",
        "interest rate",
    ],
    "companies": [
        "company",
        "corporate",
        "business",
        "ceo",
        "office",
        "factory",
    ],
    "economy": [
        "economy",
        "inflation",
        "gdp",
        "employment",
        "trade",
    ],
}


# =========================================================
# БАЗОВЫЕ ФУНКЦИИ
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    return clean_text(text).lower()


def escape_html(text):
    return html.escape(str(text), quote=False)


def shorten(text, max_len=450):
    text = clean_text(text)

    if len(text) <= max_len:
        return text

    return text[:max_len].rsplit(" ", 1)[0] + "…"


# =========================================================
# ИСТОРИЯ
# =========================================================

def load_json_file(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data
    except Exception:
        return default


def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_posted():
    data = load_json_file(POSTED_FILE, [])

    if not isinstance(data, list):
        return []

    return data


def save_posted(data):
    save_json_file(POSTED_FILE, data[-1000:])


def load_used_images():
    data = load_json_file(USED_IMAGES_FILE, [])

    if not isinstance(data, list):
        return []

    return data


def save_used_images(data):
    save_json_file(USED_IMAGES_FILE, data[-1000:])


# =========================================================
# ДАТЫ
# =========================================================

def parse_date(value):
    if not value:
        return None

    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def age_hours(value):
    dt = parse_date(value)

    if not dt:
        return 999

    now = datetime.now(timezone.utc)

    return max(0, (now - dt).total_seconds() / 3600)


# =========================================================
# HTTP
# =========================================================

def fetch(url, timeout=20):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
        )

        response.raise_for_status()

        return response

    except Exception:
        return None


# =========================================================
# RSS
# =========================================================

def parse_rss(xml_text, source):
    articles = []

    try:
        root = ET.fromstring(xml_text)

    except Exception:
        return articles

    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        description = item.findtext("description", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")

        title = clean_text(title)
        description = clean_text(description)
        link = clean_text(link)

        if not title or not link:
            continue

        articles.append(
            {
                "title": title,
                "description": description,
                "link": link,
                "published": pub_date,
                "source": source,
            }
        )

    return articles


# =========================================================
# ПЕРЕВОД НА РУССКИЙ
# =========================================================

def is_mostly_russian(text):
    text = clean_text(text)

    if not text:
        return False

    cyrillic = len(re.findall(r"[а-яё]", text.lower()))
    latin = len(re.findall(r"[a-z]", text.lower()))

    if cyrillic == 0:
        return False

    if latin == 0:
        return True

    return cyrillic >= latin * 1.2


def translate_text(text):
    """
    Перевод английского текста на русский через MyMemory.
    Если перевод не удался — возвращается оригинал.
    """

    text = clean_text(text)

    if not text:
        return ""

    # Уже русский — не переводим
    if is_mostly_russian(text):
        return text

    try:
        response = requests.get(
            "https://api.mymemory.translated.net/get",
            params={
                "q": text[:4500],
                "langpair": "en|ru",
            },
            headers=HEADERS,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        translated = (
            data.get("responseData", {})
            .get("translatedText", "")
        )

        translated = clean_text(translated)

        # Проверяем, что перевод действительно получился
        if translated and is_mostly_russian(translated):
            return translated

    except Exception as e:
        print("Translation error:", e)

    return text


def prepare_russian_article(article):
    """
    Переводим заголовок и описание один раз,
    чтобы не делать повторные запросы.
    """

    original_title = article.get("title", "")
    original_description = article.get("description", "")

    article["ru_title"] = translate_text(original_title)
    article["ru_description"] = translate_text(original_description)

    return article


# =========================================================
# АНАЛИЗ
# =========================================================

def contains_any(text, words):
    text = normalize(text)

    return any(word in text for word in words)


def extract_numbers(text):
    text = clean_text(text)

    patterns = [
        r"\$[\d,.]+\s*(?:million|billion|trillion)?",
        r"€[\d,.]+\s*(?:million|billion|trillion)?",
        r"£[\d,.]+\s*(?:million|billion|trillion)?",
        r"\b\d+(?:\.\d+)?%",
        r"\b\d+(?:\.\d+)?\s*(?:million|billion|trillion)\b",
    ]

    results = []

    for pattern in patterns:
        found = re.findall(pattern, text, flags=re.I)

        for item in found:
            item = item.strip()

            if item not in results:
                results.append(item)

    return results[:8]


def detect_companies(text):
    text = normalize(text)

    found = []

    for company in COMPANIES:
        if company in text:
            found.append(company)

    return found


def detect_category(article):
    text = normalize(
        article.get("title", "")
        + " "
        + article.get("description", "")
    )

    if contains_any(text, TECH_WORDS):
        return "Технологии"

    if contains_any(text, MARKET_WORDS):
        return "Рынки"

    if contains_any(text, FINANCE_WORDS):
        return "Финансы"

    if contains_any(text, MACRO_WORDS):
        return "Экономика"

    if contains_any(text, RUSSIA_WORDS):
        return "Россия"

    if contains_any(text, USA_WORDS):
        return "США"

    return "Бизнес"


# =========================================================
# ОЦЕНКА НОВОСТИ
# =========================================================

def source_score(source):
    source = normalize(source)

    if "reuters" in source:
        return 8

    if "market" in source:
        return 5

    if "economy" in source:
        return 5

    if "technology" in source:
        return 5

    if "business" in source:
        return 4

    return 2


def clickbait_penalty(text):
    text = normalize(text)

    count = sum(1 for word in CLICKBAIT_WORDS if word in text)

    return min(count * 3, 10)


def calculate_score(article):
    title = normalize(article.get("title", ""))
    description = normalize(article.get("description", ""))

    text = title + " " + description

    score = 0

    score += source_score(article.get("source", ""))

    if contains_any(text, CRITICAL_WORDS):
        score += 8

    if contains_any(text, MONEY_WORDS):
        score += 5

    if contains_any(text, FINANCE_WORDS):
        score += 4

    if contains_any(text, TECH_WORDS):
        score += 4

    if contains_any(text, MARKET_WORDS):
        score += 4

    if contains_any(text, MACRO_WORDS):
        score += 4

    if contains_any(text, USA_WORDS):
        score += 2

    if contains_any(text, RUSSIA_WORDS):
        score += 2

    if extract_numbers(text):
        score += 3

    if detect_companies(text):
        score += 3

    if contains_any(text, LOW_VALUE_WORDS):
        score -= 8

    score -= clickbait_penalty(title)

    age = age_hours(article.get("published"))

    if age <= 6:
        score += 5
    elif age <= 12:
        score += 4
    elif age <= 24:
        score += 2
    elif age > 48:
        score -= 10

    return score


# =========================================================
# СХОЖЕСТЬ НОВОСТЕЙ
# =========================================================

def important_words(text):
    words = re.findall(r"[a-zа-яё0-9]{4,}", normalize(text))

    stop_words = {
        "this",
        "that",
        "with",
        "from",
        "about",
        "after",
        "before",
        "their",
        "there",
        "which",
        "will",
        "would",
        "have",
        "been",
        "бизнес",
        "компания",
        "новости",
    }

    return {
        word
        for word in words
        if word not in stop_words
    }


def similarity(text1, text2):
    a = important_words(text1)
    b = important_words(text2)

    if not a or not b:
        return 0

    intersection = len(a & b)
    union = len(a | b)

    return intersection / union


def remove_similar_news(articles):
    result = []

    for article in articles:
        duplicate = False

        for existing in result:
            sim = similarity(
                article.get("title", ""),
                existing.get("title", ""),
            )

            if sim >= 0.65:
                duplicate = True
                break

        if not duplicate:
            result.append(article)

    return result


# =========================================================
# РУССКИЙ РЕДАКТОРСКИЙ ЗАГОЛОВОК
# =========================================================

def editorial_title(article):
    title = article.get("ru_title") or translate_text(
        article.get("title", "")
    )

    title = clean_text(title)

    # Убираем типичный хвост Google News
    title = re.sub(
        r"\s+[—-]\s+(Reuters|CNBC|BBC|CNN|Bloomberg|Forbes)\s*$",
        "",
        title,
        flags=re.I,
    )

    if not title:
        title = "Важная новость бизнеса"

    return title


# =========================================================
# КРАТКОЕ ОПИСАНИЕ
# =========================================================

def generate_summary(article):
    description = (
        article.get("ru_description")
        or translate_text(article.get("description", ""))
    )

    description = clean_text(description)

    if not description:
        return "Подробности события уточняются."

    return shorten(description, 430)


# =========================================================
# АНАЛИЗ "ПОЧЕМУ ЭТО ВАЖНО"
# =========================================================

def generate_analysis(article):
    text = normalize(
        article.get("title", "")
        + " "
        + article.get("description", "")
    )

    category = detect_category(article)

    if contains_any(text, CRITICAL_WORDS):
        return (
            "Событие может иметь повышенное влияние на рынок, "
            "бизнес или инвестиционные ожидания."
        )

    if contains_any(text, MARKET_WORDS):
        return (
            "Новость может повлиять на настроения инвесторов "
            "и динамику финансовых рынков."
        )

    if contains_any(text, FINANCE_WORDS):
        return (
            "Изменения в финансовом секторе могут отразиться "
            "на стоимости кредитов, капитале и деловой активности."
        )

    if contains_any(text, TECH_WORDS):
        return (
            "Событие может повлиять на развитие технологий, "
            "инвестиции и конкуренцию между компаниями."
        )

    if category == "Экономика":
        return (
            "Новость важна для оценки экономической ситуации "
            "и перспектив деловой активности."
        )

    return (
        "Событие представляет интерес для бизнеса "
        "и может повлиять на участников рынка."
    )


# =========================================================
# ХЭШТЕГИ
# =========================================================

def hashtags(article):
    text = normalize(
        article.get("title", "")
        + " "
        + article.get("description", "")
    )

    tags = ["#МРК", "#БизнесНовости"]

    category = detect_category(article)

    category_tags = {
        "Технологии": "#Технологии",
        "Рынки": "#Рынки",
        "Финансы": "#Финансы",
        "Экономика": "#Экономика",
        "Россия": "#Россия",
        "США": "#США",
        "Бизнес": "#Бизнес",
    }

    if category in category_tags:
        tags.append(category_tags[category])

    if "nvidia" in text:
        tags.append("#NVIDIA")

    if "tesla" in text:
        tags.append("#Tesla")

    if "apple" in text:
        tags.append("#Apple")

    if "microsoft" in text:
        tags.append("#Microsoft")

    if "bitcoin" in text:
        tags.append("#Bitcoin")

    return " ".join(tags[:6])


# =========================================================
# YAHOO FINANCE
# =========================================================

def yahoo_quote(ticker):
    try:
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + quote_plus(ticker)
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        result = data["chart"]["result"][0]

        meta = result.get("meta", {})

        price = meta.get("regularMarketPrice")
        previous = meta.get("previousClose")

        if price is None:
            return None

        change = None

        if previous:
            change = ((price - previous) / previous) * 100

        return {
            "ticker": ticker,
            "price": price,
            "change": change,
        }

    except Exception:
        return None


def market_snapshot(article):
    companies = detect_companies(
        article.get("title", "")
        + " "
        + article.get("description", "")
    )

    results = []

    for company in companies[:3]:
        ticker = COMPANIES.get(company)

        if not ticker:
            continue

        quote = yahoo_quote(ticker)

        if quote:
            results.append(quote)

    return results


def global_market_snapshot():
    instruments = [
        ("S&P 500", "^GSPC"),
        ("NASDAQ", "^IXIC"),
        ("Brent", "BZ=F"),
        ("Bitcoin", "BTC-USD"),
    ]

    results = []

    for name, ticker in instruments:
        quote = yahoo_quote(ticker)

        if quote:
            quote["name"] = name
            results.append(quote)

    return results


def currency_rate():
    quote = yahoo_quote("EURUSD=X")

    if not quote:
        return None

    return quote.get("price")


# =========================================================
# ИЗОБРАЖЕНИЯ
# =========================================================

def add_image(images, url, score=0):
    if not url:
        return

    url = url.strip()

    if not url.startswith("http"):
        return

    if url not in [x["url"] for x in images]:
        images.append(
            {
                "url": url,
                "score": score,
            }
        )


def extract_srcset(value):
    results = []

    if not value:
        return results

    for part in value.split(","):
        part = part.strip()

        if not part:
            continue

        url = part.split(" ")[0].strip()

        if url.startswith("http"):
            results.append(url)

    return results


def extract_images(page_url, article):
    images = []

    response = fetch(page_url, timeout=20)

    if not response:
        return images

    content = response.text

    # og:image
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]

    for pattern in patterns:
        for match in re.findall(pattern, content, flags=re.I):
            add_image(images, match, 10)

    # JSON-LD
    jsonld_matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content,
        flags=re.I | re.S,
    )

    for block in jsonld_matches:
        try:
            data = json.loads(block)

            objects = data if isinstance(data, list) else [data]

            for obj in objects:
                if not isinstance(obj, dict):
                    continue

                image = obj.get("image")

                if isinstance(image, str):
                    add_image(images, image, 8)

                elif isinstance(image, list):
                    for item in image:
                        if isinstance(item, str):
                            add_image(images, item, 8)

                elif isinstance(image, dict):
                    image_url = image.get("url")

                    if image_url:
                        add_image(images, image_url, 8)

        except Exception:
            pass

    # img
    img_tags = re.findall(
        r"<img\b[^>]*>",
        content,
        flags=re.I,
    )

    for tag in img_tags[:80]:
        src_matches = re.findall(
            r'(?:src|data-src|data-original)=["\']([^"\']+)',
            tag,
            flags=re.I,
        )

        for src in src_matches:
            add_image(images, src, 4)

        srcset_matches = re.findall(
            r'srcset=["\']([^"\']+)',
            tag,
            flags=re.I,
        )

        for srcset in srcset_matches:
            for src in extract_srcset(srcset):
                add_image(images, src, 5)

    return images


def image_score(url, article):
    url_lower = normalize(url)

    text = normalize(
        article.get("title", "")
        + " "
        + article.get("description", "")
    )

    score = 0

    if any(x in url_lower for x in ["logo", "icon", "avatar", "sprite"]):
        score -= 10

    if any(x in url_lower for x in ["thumb", "thumbnail"]):
        score -= 2

    for theme, words in IMAGE_THEMES.items():
        if any(word in text for word in words):
            if any(word in url_lower for word in words):
                score += 5

    if any(
        x in url_lower
        for x in [
            "photo",
            "image",
            "media",
            "article",
            "news",
        ]
    ):
        score += 2

    return score


def get_best_image(article):
    candidates = extract_images(
        article.get("link", ""),
        article,
    )

    if not candidates:
        return None

    for candidate in candidates:
        candidate["score"] += image_score(
            candidate["url"],
            article,
        )

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    used_images = load_used_images()

    for candidate in candidates:
        url = candidate["url"]

        image_hash = hashlib.sha256(
            url.encode("utf-8")
        ).hexdigest()

        if image_hash not in used_images:
            return url

    return None


# =========================================================
# TELEGRAM
# =========================================================

def tg_url(method):
    return (
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    )


def send_message(text, reply_markup=None):
    payload = {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    if reply_markup:
        payload["reply_markup"] = json.dumps(
            reply_markup,
            ensure_ascii=False,
        )

    try:
        response = requests.post(
            tg_url("sendMessage"),
            data=payload,
            timeout=30,
        )

        print(
            "Telegram message:",
            response.status_code,
            response.text[:500],
        )

        return response.ok

    except Exception as e:
        print("Telegram error:", e)

        return False


def send_photo(image_url, caption, reply_markup=None):
    try:
        image_response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=20,
        )

        image_response.raise_for_status()

        content = image_response.content

        if len(content) > MAX_IMAGE_SIZE:
            print("Image is too large")

            return False

        files = {
            "photo": (
                "news.jpg",
                content,
                image_response.headers.get(
                    "Content-Type",
                    "image/jpeg",
                ),
            )
        }

        data = {
            "chat_id": CHANNEL,
            "caption": caption,
            "parse_mode": "HTML",
        }

        if reply_markup:
            data["reply_markup"] = json.dumps(
                reply_markup,
                ensure_ascii=False,
            )

        response = requests.post(
            tg_url("sendPhoto"),
            data=data,
            files=files,
            timeout=40,
        )

        print(
            "Telegram photo:",
            response.status_code,
            response.text[:500],
        )

        return response.ok

    except Exception as e:
        print("Photo error:", e)

        return False


# =========================================================
# ПОСТ
# =========================================================

def build_post(article):
    # Сначала переводим всю новость
    prepare_russian_article(article)

    title = editorial_title(article)
    summary = generate_summary(article)

    category = detect_category(article)

    original_text = (
        article.get("title", "")
        + " "
        + article.get("description", "")
    )

    numbers = extract_numbers(original_text)

    analysis = generate_analysis(article)

    company_data = market_snapshot(article)

    lines = []

    # Заголовок
    lines.append(
        f"<b>📰 {escape_html(title)}</b>"
    )

    lines.append("")

    # Краткое описание
    lines.append(
        f"{escape_html(summary)}"
    )

    # Важные цифры
    if numbers:
        lines.append("")
        lines.append("<b>📊 Ключевые показатели:</b>")

        for number in numbers[:5]:
            lines.append(
                f"• {escape_html(number)}"
            )

    # Компания / рынок
    if company_data:
        lines.append("")
        lines.append("<b>💹 Рынок:</b>")

        for item in company_data:
            price = item.get("price")
            change = item.get("change")

            if price is None:
                continue

            if change is not None:
                sign = "+" if change >= 0 else ""

                lines.append(
                    f"• {item['ticker']}: "
                    f"{price:.2f} "
                    f"({sign}{change:.2f}%)"
                )

            else:
                lines.append(
                    f"• {item['ticker']}: {price:.2f}"
                )

    # Анализ
    lines.append("")
    lines.append("<b>💡 Почему это важно:</b>")
    lines.append(
        escape_html(analysis)
    )

    # Категория
    lines.append("")
    lines.append(
        f"<b>Категория:</b> {escape_html(category)}"
    )

    # Источник
    source = article.get("source", "Источник")

    lines.append("")
    lines.append(
        f"<b>Источник:</b> {escape_html(source)}"
    )

    return "\n".join(lines)


def keyboard(article):
    link = article.get("link")

    if not link:
        return None

    return {
        "inline_keyboard": [
            [
                {
                    "text": "🔗 Читать источник",
                    "url": link,
                }
            ]
        ]
    }


# =========================================================
# ПРОВЕРКА КАЧЕСТВА
# =========================================================

def quality_check(post):
    if not post:
        return False

    # Telegram caption имеет ограничение.
    if len(post) > 1000:
        return False

    # Проверяем, что в посте есть кириллица
    cyrillic = len(
        re.findall(r"[а-яё]", post.lower())
    )

    if cyrillic < 20:
        return False

    return True


# =========================================================
# ВЫБОР НОВОСТЕЙ
# =========================================================

def select_articles(articles, posted):
    candidates = []

    for article in articles:
        link = article.get("link", "")

        if not link:
            continue

        if link in posted:
            continue

        if age_hours(article.get("published")) > MAX_NEWS_AGE_HOURS:
            continue

        article["score"] = calculate_score(article)

        if article["score"] < MIN_SCORE:
            continue

        candidates.append(article)

    candidates.sort(
        key=lambda x: x.get("score", 0),
        reverse=True,
    )

    candidates = candidates[:MAX_CANDIDATES]

    candidates = remove_similar_news(candidates)

    # Немного балансируем категории
    selected = []

    category_count = {}

    for article in candidates:
        category = detect_category(article)

        current_count = category_count.get(category, 0)

        if current_count >= 2:
            continue

        selected.append(article)

        category_count[category] = current_count + 1

        if len(selected) >= MAX_POSTS_PER_RUN:
            break

    return selected


# =========================================================
# MAIN
# =========================================================

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is not configured")
        return

    print("======================================")
    print("МРК BUSINESS NEWS BOT 6.1")
    print("Русский перевод включён")
    print("======================================")

    posted = load_posted()

    all_articles = []

    # -----------------------------------------------------
    # Загружаем RSS
    # -----------------------------------------------------

    for source, url in RSS_FEEDS:
        print("Loading:", source)

        response = fetch(url)

        if not response:
            print("Failed:", source)
            continue

        articles = parse_rss(
            response.text,
            source,
        )

        print(
            source,
            "articles:",
            len(articles),
        )

        all_articles.extend(articles)

    print(
        "Total RSS articles:",
        len(all_articles),
    )

    # -----------------------------------------------------
    # Убираем дубли по ссылкам
    # -----------------------------------------------------

    unique = {}

    for article in all_articles:
        link = article.get("link")

        if link:
            unique[link] = article

    all_articles = list(unique.values())

    print(
        "Unique articles:",
        len(all_articles),
    )

    # -----------------------------------------------------
    # Выбор лучших
    # -----------------------------------------------------

    selected = select_articles(
        all_articles,
        posted,
    )

    print(
        "Selected:",
        len(selected),
    )

    # -----------------------------------------------------
    # Публикация
    # -----------------------------------------------------

    used_images = load_used_images()

    for article in selected:

        try:
            print("")
            print(
                "Publishing:",
                article.get("title"),
            )

            post = build_post(article)

            # Хэштеги добавляем после формирования текста
            tags = hashtags(article)

            full_post = (
                post
                + "\n\n"
                + tags
            )

            # Если слишком длинный — сокращаем описание
            if len(full_post) > 1000:
                article["ru_description"] = shorten(
                    article.get("ru_description", ""),
                    260,
                )

                post = build_post(article)

                full_post = (
                    post
                    + "\n\n"
                    + tags
                )

            if not quality_check(full_post):
                print("Quality check failed")

                continue

            # -------------------------------------------------
            # Ищем тематическую картинку
            # -------------------------------------------------

            image_url = get_best_image(article)

            success = False

            if image_url:
                print(
                    "Image found:",
                    image_url[:150],
                )

                success = send_photo(
                    image_url,
                    full_post,
                    keyboard(article),
                )

                if success:
                    image_hash = hashlib.sha256(
                        image_url.encode("utf-8")
                    ).hexdigest()

                    if image_hash not in used_images:
                        used_images.append(image_hash)

            # -------------------------------------------------
            # Если фото не отправилось — отправляем текст
            # -------------------------------------------------

            if not success:
                print(
                    "Photo failed or unavailable. "
                    "Sending text."
                )

                success = send_message(
                    full_post,
                    keyboard(article),
                )

            # -------------------------------------------------
            # Сохраняем историю
            # -------------------------------------------------

            if success:
                link = article.get("link")

                if link and link not in posted:
                    posted.append(link)

                save_posted(posted)
                save_used_images(used_images)

                print("SUCCESS:", article.get("title"))

            else:
                print(
                    "FAILED:",
                    article.get("title"),
                )

            # Небольшая пауза
            time.sleep(2)

        except Exception as e:
            print(
                "ARTICLE ERROR:",
                repr(e),
            )

    print("")
    print("Bot finished.")


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
