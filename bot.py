import os
import re
import json
import time
import hashlib
import html
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
import xml.etree.ElementTree as ET


# =========================================================
# МРК — БИЗНЕС НОВОСТИ
# VERSION 5.1
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")

MAX_POSTS_PER_RUN = 2
MIN_SCORE = 7
MAX_CANDIDATES = 60
MAX_NEWS_AGE_HOURS = 48

# Оставляем запас относительно лимита Telegram.
MAX_IMAGE_SIZE = 9 * 1024 * 1024

POSTED_FILE = "posted.json"
USED_IMAGES_FILE = "used_images.json"


# =========================================================
# RSS
# =========================================================

RSS_FEEDS = [
    (
        "Reuters",
        "https://news.google.com/rss/search?q=business+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "USA",
        "https://news.google.com/rss/search?q=US+business+economy+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Russia",
        "https://news.google.com/rss/search?q=Russia+business+economy+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Markets",
        "https://news.google.com/rss/search?q=stock+market+finance+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Economy",
        "https://news.google.com/rss/search?q=economy+inflation+interest+rates+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Technology",
        "https://news.google.com/rss/search?q=technology+AI+chips+business+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Business",
        "https://news.google.com/rss/search?q=companies+corporate+business+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
]


# =========================================================
# КЛЮЧЕВЫЕ СЛОВА
# =========================================================

COMPANY_WORDS = [
    "company", "companies", "corporation", "corp", "firm",
    "business", "ceo", "executive", "shares", "revenue",
    "profit", "earnings", "merger", "acquisition", "startup",
    "ipo", "investor", "investment"
]

CRITICAL_WORDS = [
    "bankruptcy", "bankrupt", "collapse", "crisis",
    "sanctions", "sanction", "default", "war",
    "emergency", "fraud", "investigation", "lawsuit",
    "tariff", "tariffs", "ban", "banned", "recall"
]

FINANCE_WORDS = [
    "bank", "banks", "fed", "federal reserve", "ecb",
    "central bank", "interest rate", "rates", "inflation",
    "deflation", "currency", "dollar", "euro",
    "bond", "bonds", "debt", "credit", "loan",
    "finance", "financial"
]

MONEY_WORDS = [
    "million", "billion", "trillion",
    "million dollars", "billion dollars",
    "revenue", "profit", "loss", "earnings",
    "valuation", "investment", "funding"
]

TECH_WORDS = [
    "ai", "artificial intelligence", "technology",
    "software", "chip", "chips", "semiconductor",
    "semiconductors", "data center", "data centres",
    "cloud", "robot", "robotics", "automation",
    "nvidia", "microsoft", "google", "openai", "apple",
    "meta", "amazon", "intel", "amd"
]

USA_WORDS = [
    "usa", "u.s.", "us ", "united states",
    "washington", "new york", "american", "america",
    "california", "texas", "wall street"
]

RUSSIA_WORDS = [
    "russia", "russian", "moscow",
    "gazprom", "rosneft", "sberbank",
    "yandex", "lukoil", "novatek",
    "vtb", "surgutneftegas", "magnit",
    "ozon", "wildberries"
]

MARKET_MOVE_WORDS = [
    "rise", "rises", "rose", "rally",
    "surge", "surges", "jump", "jumps",
    "gain", "gains", "drop", "drops",
    "fall", "falls", "fell", "plunge",
    "plunges", "decline", "declines",
    "selloff", "sell-off", "record high",
    "record low"
]

MACRO_WORDS = [
    "economy", "economic", "inflation",
    "gdp", "employment", "jobs",
    "unemployment", "interest rates",
    "rate cut", "rate hike",
    "recession", "growth", "trade",
    "tariff", "tariffs"
]

CLICKBAIT_WORDS = [
    "you won't believe",
    "shocking",
    "unbelievable",
    "secret",
    "what happens next",
    "must see",
    "click here",
    "breaking!!!"
]

LOW_VALUE_WORDS = [
    "horoscope",
    "celebrity",
    "movie",
    "sports",
    "football",
    "soccer",
    "recipe",
    "weather",
    "lottery",
    "entertainment"
]


# =========================================================
# ТЕМАТИКА ИЗОБРАЖЕНИЙ
# =========================================================

IMAGE_THEME_RULES = {
    "technology": [
        "ai", "artificial intelligence",
        "technology", "software", "chip", "chips",
        "semiconductor", "semiconductors",
        "data center", "data centre",
        "cloud", "robot", "robotics",
        "nvidia", "microsoft", "google",
        "openai", "apple", "meta", "amazon",
        "intel", "amd"
    ],

    "auto": [
        "tesla", "car", "cars", "automotive",
        "vehicle", "vehicles", "ev",
        "electric vehicle", "electric vehicles",
        "automobile", "automobiles",
        "ford", "toyota", "volkswagen",
        "bmw", "mercedes", "gm"
    ],

    "energy": [
        "oil", "gas", "energy", "opec",
        "crude", "refinery", "refinery",
        "pipeline", "petroleum",
        "natural gas", "lng",
        "solar", "wind power",
        "electricity"
    ],

    "markets": [
        "stock", "stocks", "stock market",
        "trading", "trader", "traders",
        "exchange", "wall street",
        "nasdaq", "dow jones", "s&p",
        "shares", "equity", "equities",
        "market"
    ],

    "finance": [
        "bank", "banks", "banking",
        "fed", "federal reserve",
        "ecb", "central bank",
        "dollar", "euro", "currency",
        "finance", "financial",
        "credit", "loan", "bond", "bonds"
    ],

    "russia": [
        "russia", "russian", "moscow",
        "gazprom", "rosneft", "sberbank",
        "yandex", "lukoil", "novatek",
        "vtb", "surgutneftegas",
        "magnit", "ozon", "wildberries"
    ],

    "usa": [
        "usa", "u.s.", "united states",
        "washington", "new york",
        "american", "america",
        "california", "texas",
        "wall street"
    ],

    "real_estate": [
        "real estate", "property",
        "housing", "house", "homes",
        "apartment", "apartments",
        "construction", "building"
    ],

    "retail": [
        "retail", "shopping", "store",
        "stores", "consumer",
        "walmart", "costco", "amazon",
        "target", "sales"
    ]
}


GENERIC_IMAGE_WORDS = [
    "logo",
    "logos",
    "icon",
    "icons",
    "avatar",
    "favicon",
    "sprite",
    "placeholder",
    "default-image",
    "default_image",
    "no-image",
    "no_image",
    "thumbnail",
    "thumb",
    "banner",
    "advertisement",
    "ads",
    "pixel"
]


# =========================================================
# HTTP
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/128.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}


# =========================================================
# БАЗОВЫЕ ФУНКЦИИ
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
    text = re.sub(r"[^\w\s\-\.]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def escape_html(text):
    return html.escape(text or "", quote=False)


def shorten_title(title, max_len=180):
    title = clean_text(title)

    if len(title) <= max_len:
        return title

    return title[:max_len - 3].rstrip() + "..."


# =========================================================
# ИСТОРИЯ
# =========================================================

def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted[-1000:], f, ensure_ascii=False, indent=2)


def load_used_images():
    if not os.path.exists(USED_IMAGES_FILE):
        return []

    try:
        with open(USED_IMAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_used_images(images):
    with open(USED_IMAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(images[-2000:], f, ensure_ascii=False, indent=2)


# =========================================================
# ДАТА
# =========================================================

def parse_date(value):
    if not value:
        return None

    value = value.strip()

    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt

        except Exception:
            continue

    return None


def get_age_hours(dt):
    if not dt:
        return 0

    now = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    seconds = (now - dt).total_seconds()

    return max(0, seconds / 3600)


# =========================================================
# GOOGLE NEWS RSS
# =========================================================

def get_google_news_rss(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        r.raise_for_status()

        return r.text

    except Exception as e:
        print("RSS ERROR:", e)
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
            item.findtext("description", "")
        )

        pub_date = clean_text(
            item.findtext("pubDate", "")
        )

        source = clean_text(
            item.findtext("{http://search.yahoo.com/mrss/}source", "")
        )

        if not source:
            source = feed_name

        if not title or not link:
            continue

        dt = parse_date(pub_date)

        articles.append({
            "title": title,
            "description": description,
            "url": link,
            "date": dt,
            "source": source,
            "feed": feed_name
        })

    return articles


# =========================================================
# КАТЕГОРИЯ
# =========================================================

def detect_category(article):
    text = normalize(
        article.get("title", "") + " " +
        article.get("description", "")
    )

    scores = {
        "Технологии": 0,
        "Финансы": 0,
        "Рынки": 0,
        "Энергетика": 0,
        "Россия": 0,
        "США": 0,
        "Экономика": 0,
        "Бизнес": 0
    }

    for word in TECH_WORDS:
        if word in text:
            scores["Технологии"] += 3

    for word in FINANCE_WORDS:
        if word in text:
            scores["Финансы"] += 3

    for word in MARKET_MOVE_WORDS:
        if word in text:
            scores["Рынки"] += 2

    for word in RUSSIA_WORDS:
        if word in text:
            scores["Россия"] += 3

    for word in USA_WORDS:
        if word in text:
            scores["США"] += 2

    for word in MACRO_WORDS:
        if word in text:
            scores["Экономика"] += 2

    for word in COMPANY_WORDS:
        if word in text:
            scores["Бизнес"] += 1

    if any(
        x in text
        for x in ["oil", "gas", "energy", "opec", "crude"]
    ):
        scores["Энергетика"] += 5

    category = max(
        scores,
        key=scores.get
    )

    if scores[category] == 0:
        category = "Бизнес"

    return category


# =========================================================
# ОЦЕНКА НОВОСТИ
# =========================================================

def calculate_score(article):
    title = normalize(article.get("title", ""))
    description = normalize(article.get("description", ""))

    text = title + " " + description

    score = 0

    # Свежесть
    age = get_age_hours(article.get("date"))

    if age <= 3:
        score += 5
    elif age <= 8:
        score += 4
    elif age <= 18:
        score += 3
    elif age <= 30:
        score += 2
    elif age <= 48:
        score += 1

    # Бизнес
    for word in COMPANY_WORDS:
        if word in text:
            score += 1

    # Деньги
    for word in MONEY_WORDS:
        if word in text:
            score += 2

    # Финансы
    for word in FINANCE_WORDS:
        if word in text:
            score += 2

    # Технологии
    for word in TECH_WORDS:
        if word in text:
            score += 2

    # Макроэкономика
    for word in MACRO_WORDS:
        if word in text:
            score += 2

    # Резкие движения рынка
    for word in MARKET_MOVE_WORDS:
        if word in text:
            score += 2

    # Крупные события
    for word in CRITICAL_WORDS:
        if word in text:
            score += 4

    # США / Россия
    for word in USA_WORDS:
        if word in text:
            score += 1

    for word in RUSSIA_WORDS:
        if word in text:
            score += 2

    score -= clickbait_penalty(text)

    for word in LOW_VALUE_WORDS:
        if word in text:
            score -= 6

    return score


def clickbait_penalty(text):
    penalty = 0

    for word in CLICKBAIT_WORDS:
        if word in text:
            penalty += 4

    if text.count("!") >= 3:
        penalty += 3

    return penalty


# =========================================================
# ВАЖНЫЕ СЛОВА
# =========================================================

def important_words(text):
    text = normalize(text)

    words = re.findall(
        r"\b[a-zа-яё0-9][a-zа-яё0-9\-]{3,}\b",
        text,
        flags=re.IGNORECASE
    )

    stop_words = {
        "this", "that", "with", "from", "have",
        "will", "about", "after", "before",
        "into", "their", "they", "them",
        "were", "been", "said", "says",
        "which", "when", "where", "what",
        "как", "это", "для", "что", "при",
        "после", "перед", "также", "будет",
        "был", "была", "были"
    }

    result = []

    for word in words:
        if word not in stop_words and word not in result:
            result.append(word)

    return result[:25]


# =========================================================
# СХОЖЕСТЬ НОВОСТЕЙ
# =========================================================

def similarity(a, b):
    a_words = set(
        important_words(a.get("title", ""))
    )

    b_words = set(
        important_words(b.get("title", ""))
    )

    if not a_words or not b_words:
        return 0

    intersection = len(a_words & b_words)
    union = len(a_words | b_words)

    return intersection / union if union else 0


def remove_similar_news(articles):
    result = []

    for article in articles:

        duplicate = False

        for existing in result:

            if similarity(article, existing) >= 0.55:
                duplicate = True
                break

        if not duplicate:
            result.append(article)

    return result


# =========================================================
# ПЕРЕВОД
# =========================================================

def translate_text(text):
    text = clean_text(text)

    if not text:
        return ""

    # Уже русский
    cyrillic = len(
        re.findall(r"[а-яё]", text.lower())
    )

    latin = len(
        re.findall(r"[a-z]", text.lower())
    )

    if cyrillic > latin:
        return text

    try:
        url = "https://api.mymemory.translated.net/get"

        params = {
            "q": text[:4500],
            "langpair": "en|ru"
        }

        r = requests.get(
            url,
            params=params,
            timeout=20
        )

        data = r.json()

        translated = data.get(
            "responseData", {}
        ).get(
            "translatedText", ""
        )

        if translated:
            return clean_text(translated)

    except Exception as e:
        print("TRANSLATION ERROR:", e)

    return text


# =========================================================
# АНАЛИЗ
# =========================================================

def generate_analysis(article):
    category = detect_category(article)

    title = article.get("title", "")
    text = normalize(
        title + " " +
        article.get("description", "")
    )

    reasons = []

    if any(
        word in text
        for word in CRITICAL_WORDS
    ):
        reasons.append(
            "событие может существенно повлиять на рынок"
        )

    if any(
        word in text
        for word in FINANCE_WORDS
    ):
        reasons.append(
            "новость связана с финансовыми условиями"
        )

    if any(
        word in text
        for word in MARKET_MOVE_WORDS
    ):
        reasons.append(
            "в публикации отмечается заметное движение рынка"
        )

    if any(
        word in text
        for word in TECH_WORDS
    ):
        reasons.append(
            "событие имеет значение для технологического сектора"
        )

    if any(
        word in text
        for word in RUSSIA_WORDS
    ):
        reasons.append(
            "новость связана с российским рынком"
        )

    if any(
        word in text
        for word in USA_WORDS
    ):
        reasons.append(
            "событие связано с экономикой США"
        )

    if not reasons:
        reasons.append(
            "новость может представлять интерес для деловой аудитории"
        )

    return (
        f"<b>Почему это важно:</b> "
        f"{reasons[0].capitalize()}."
    )


# =========================================================
# ХЭШТЕГИ
# =========================================================

def generate_hashtags(article):
    category = detect_category(article)

    hashtags = {
        "Технологии": "#технологии #AI #бизнес",
        "Финансы": "#финансы #экономика #деньги",
        "Рынки": "#рынки #акции #инвестиции",
        "Энергетика": "#энергетика #нефть #газ",
        "Россия": "#Россия #бизнес #экономика",
        "США": "#США #экономика #бизнес",
        "Экономика": "#экономика #рынки #бизнес",
        "Бизнес": "#бизнес #экономика #компании"
    }

    return hashtags.get(
        category,
        "#бизнес #экономика"
    )


# =========================================================
# ФОРМАТ ПОСТА
# =========================================================

def format_post(article):
    title_ru = translate_text(
        article.get("title", "")
    )

    description_ru = translate_text(
        article.get("description", "")
    )

    title_ru = shorten_title(
        title_ru,
        180
    )

    description_ru = clean_text(
        description_ru
    )

    if len(description_ru) > 500:
        description_ru = (
            description_ru[:497].rstrip()
            + "..."
        )

    category = detect_category(article)

    analysis = generate_analysis(article)

    hashtags = generate_hashtags(article)

    source = clean_text(
        article.get("source", "Источник")
    )

    parts = []

    parts.append(
        f"<b>🔥 {escape_html(title_ru)}</b>"
    )

    if description_ru:
        parts.append(
            escape_html(description_ru)
        )

    parts.append(
        f"<b>Категория:</b> "
        f"#{escape_html(category.replace(' ', ''))}"
    )

    parts.append(analysis)

    parts.append(
        f"<i>Источник: {escape_html(source)}</i>"
    )

    parts.append(hashtags)

    return "\n\n".join(parts)


# =========================================================
# КНОПКА
# =========================================================

def get_keyboard(article):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📰 Читать источник",
                    "url": article.get("url", "")
                }
            ]
        ]
    }


# =========================================================
# IMAGE CANDIDATES
# =========================================================

def add_image_candidate(
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

    if not url.startswith(("http://", "https://")):
        return

    candidates.append({
        "url": url,
        "source_type": source_type,
        "alt": clean_text(alt),
        "title": clean_text(title),
        "context": clean_text(context)
    })


def extract_srcset(srcset):
    result = []

    if not srcset:
        return result

    for item in srcset.split(","):
        item = item.strip()

        if not item:
            continue

        parts = item.split()

        if parts:
            result.append(parts[0])

    return result


def extract_image_candidates(
    page_html,
    page_url
):
    candidates = []

    # -----------------------------------------------------
    # OG IMAGE
    # -----------------------------------------------------

    og_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
    ]

    for pattern in og_patterns:
        for match in re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        ):
            add_image_candidate(
                candidates,
                urljoin(page_url, match),
                "og"
            )

    # -----------------------------------------------------
    # TWITTER IMAGE
    # -----------------------------------------------------

    twitter_patterns = [
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
    ]

    for pattern in twitter_patterns:
        for match in re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        ):
            add_image_candidate(
                candidates,
                urljoin(page_url, match),
                "twitter"
            )

    # -----------------------------------------------------
    # IMAGE_SRC
    # -----------------------------------------------------

    image_src_patterns = [
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)',
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']image_src["\']'
    ]

    for pattern in image_src_patterns:
        for match in re.findall(
            pattern,
            page_html,
            flags=re.IGNORECASE
        ):
            add_image_candidate(
                candidates,
                urljoin(page_url, match),
                "image_src"
            )

    # -----------------------------------------------------
    # JSON-LD IMAGE
    # -----------------------------------------------------

    jsonld_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL
    )

    for block in jsonld_blocks:

        try:
            data = json.loads(
                html.unescape(block.strip())
            )

            objects = (
                data
                if isinstance(data, list)
                else [data]
            )

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                image = obj.get("image")

                if isinstance(image, str):
                    add_image_candidate(
                        candidates,
                        urljoin(page_url, image),
                        "jsonld"
                    )

                elif isinstance(image, list):

                    for img in image[:5]:

                        if isinstance(img, str):
                            add_image_candidate(
                                candidates,
                                urljoin(page_url, img),
                                "jsonld"
                            )

                        elif isinstance(img, dict):
                            img_url = img.get("url")

                            if img_url:
                                add_image_candidate(
                                    candidates,
                                    urljoin(
                                        page_url,
                                        img_url
                                    ),
                                    "jsonld"
                                )

                elif isinstance(image, dict):

                    img_url = image.get("url")

                    if img_url:
                        add_image_candidate(
                            candidates,
                            urljoin(
                                page_url,
                                img_url
                            ),
                            "jsonld"
                        )

        except Exception:
            continue

    # -----------------------------------------------------
    # FIGURE / IMG
    # -----------------------------------------------------

    img_pattern = re.compile(
        r"<img\b([^>]+)>",
        flags=re.IGNORECASE | re.DOTALL
    )

    for match in img_pattern.finditer(page_html):

        attrs = match.group(1)

        src = ""

        src_match = re.search(
            r'\bsrc=["\']([^"\']+)',
            attrs,
            flags=re.IGNORECASE
        )

        if src_match:
            src = src_match.group(1)

        if not src:

            data_src_match = re.search(
                r'\bdata-src=["\']([^"\']+)',
                attrs,
                flags=re.IGNORECASE
            )

            if data_src_match:
                src = data_src_match.group(1)

        if not src:
            data_lazy_match = re.search(
                r'\bdata-lazy-src=["\']([^"\']+)',
                attrs,
                flags=re.IGNORECASE
            )

            if data_lazy_match:
                src = data_lazy_match.group(1)

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

        # Контекст вокруг изображения
        start = max(
            0,
            match.start() - 700
        )

        end = min(
            len(page_html),
            match.end() + 700
        )

        context = clean_text(
            page_html[start:end]
        )

        add_image_candidate(
            candidates,
            urljoin(page_url, src),
            "img",
            alt=alt,
            title=title,
            context=context
        )

        # srcset
        srcset_match = re.search(
            r'\bsrcset=["\']([^"\']+)',
            attrs,
            flags=re.IGNORECASE
        )

        if srcset_match:

            for srcset_url in extract_srcset(
                srcset_match.group(1)
            ):
                add_image_candidate(
                    candidates,
                    urljoin(
                        page_url,
                        srcset_url
                    ),
                    "srcset",
                    alt=alt,
                    title=title,
                    context=context
                )

    # -----------------------------------------------------
    # Удаляем дубликаты
    # -----------------------------------------------------

    unique = []
    seen = set()

    for candidate in candidates:

        url = candidate["url"]

        if url in seen:
            continue

        seen.add(url)
        unique.append(candidate)

    return unique


# =========================================================
# ПОЛУЧЕНИЕ КАНДИДАТОВ ИЗ СТРАНИЦЫ
# =========================================================

def get_article_images(article):
    url = article.get("url")

    if not url:
        return []

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        r.raise_for_status()

        return extract_image_candidates(
            r.text,
            r.url
        )

    except Exception as e:
        print(
            "ARTICLE IMAGE ERROR:",
            article.get("title"),
            e
        )

        return []


# =========================================================
# ТЕМАТИЧЕСКИЙ СКОРИНГ КАРТИНКИ
# =========================================================

def get_article_image_context(article):
    title = article.get("title", "")
    description = article.get("description", "")

    category = detect_category(article)

    text = normalize(
        title + " " +
        description
    )

    return {
        "text": text,
        "title": normalize(title),
        "description": normalize(description),
        "category": category
    }


def image_candidate_score(
    article,
    candidate
):
    context = get_article_image_context(
        article
    )

    article_text = context["text"]
    article_title = context["title"]
    category = context["category"]

    metadata = normalize(
        candidate.get("alt", "") + " " +
        candidate.get("title", "") + " " +
        candidate.get("context", "") + " " +
        candidate.get("url", "")
    )

    score = 0

    # -----------------------------------------------------
    # Приоритет официальных изображений
    # -----------------------------------------------------

    source_type = candidate.get(
        "source_type",
        ""
    )

    source_scores = {
        "og": 6,
        "twitter": 5,
        "jsonld": 5,
        "image_src": 4,
        "rss": 4,
        "srcset": 3,
        "img": 2
    }

    score += source_scores.get(
        source_type,
        1
    )

    # -----------------------------------------------------
    # Ключевые слова темы
    # -----------------------------------------------------

    category_map = {
        "Технологии": "technology",
        "Финансы": "finance",
        "Рынки": "markets",
        "Энергетика": "energy",
        "Россия": "russia",
        "США": "usa"
    }

    theme = category_map.get(
        category
    )

    if theme:

        for word in IMAGE_THEME_RULES.get(
            theme,
            []
        ):
            if word in metadata:
                score += 5

    # -----------------------------------------------------
    # Совпадения важных слов статьи
    # -----------------------------------------------------

    article_words = important_words(
        article.get("title", "") + " " +
        article.get("description", "")
    )

    for word in article_words:

        if len(word) < 4:
            continue

        if word in metadata:
            score += 2

    # -----------------------------------------------------
    # Особенно сильное совпадение с заголовком
    # -----------------------------------------------------

    title_words = important_words(
        article.get("title", "")
    )

    for word in title_words:

        if len(word) < 5:
            continue

        if word in metadata:
            score += 4

    # -----------------------------------------------------
    # Бренды / компании
    # -----------------------------------------------------

    company_candidates = [
        "nvidia",
        "microsoft",
        "google",
        "apple",
        "amazon",
        "meta",
        "openai",
        "tesla",
        "intel",
        "amd",
        "ford",
        "toyota",
        "volkswagen",
        "gazprom",
        "rosneft",
        "sberbank",
        "yandex",
        "lukoil",
        "novatek",
        "walmart",
        "costco"
    ]

    for company in company_candidates:

        if company in article_text:

            if company in metadata:
                score += 10

    # -----------------------------------------------------
    # Плохие / технические картинки
    # -----------------------------------------------------

    for word in GENERIC_IMAGE_WORDS:

        if word in metadata:
            score -= 8

    # -----------------------------------------------------
    # Очень короткий URL
    # -----------------------------------------------------

    if len(candidate.get("url", "")) < 30:
        score -= 2

    return score


def rank_image_candidates(
    article,
    candidates
):
    scored = []

    for candidate in candidates:

        score = image_candidate_score(
            article,
            candidate
        )

        item = dict(candidate)
        item["score"] = score

        scored.append(item)

    scored.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return scored


# =========================================================
# ХЭШ ИЗОБРАЖЕНИЯ
# =========================================================

def image_hash(content):
    return hashlib.sha256(
        content
    ).hexdigest()


# =========================================================
# ЗАГРУЗКА КАРТИНКИ
# =========================================================

def download_image(url):
    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=25,
            stream=True
        )

        r.raise_for_status()

        content_type = (
            r.headers.get(
                "Content-Type",
                ""
            )
            .lower()
            .split(";")[0]
        )

        allowed_types = {
            "image/jpeg",
            "image/jpg",
            "image/png"
        }

        if content_type not in allowed_types:
            print(
                "SKIP IMAGE TYPE:",
                content_type,
                url
            )
            return None

        content_length = r.headers.get(
            "Content-Length"
        )

        if content_length:

            try:
                if int(content_length) > MAX_IMAGE_SIZE:
                    print(
                        "SKIP IMAGE SIZE:",
                        url
                    )
                    return None

            except Exception:
                pass

        chunks = []
        total = 0

        for chunk in r.iter_content(
            chunk_size=64 * 1024
        ):

            if not chunk:
                continue

            total += len(chunk)

            if total > MAX_IMAGE_SIZE:
                print(
                    "IMAGE TOO LARGE:",
                    url
                )
                return None

            chunks.append(chunk)

        content = b"".join(chunks)

        if len(content) < 5000:
            return None

        return {
            "content": content,
            "content_type": content_type
        }

    except Exception as e:

        print(
            "DOWNLOAD IMAGE ERROR:",
            e
        )

        return None


# =========================================================
# ПОИСК УНИКАЛЬНОЙ ТЕМАТИЧЕСКОЙ КАРТИНКИ
# =========================================================

def find_unique_image(
    article,
    used_images
):
    candidates = get_article_images(
        article
    )

    if not candidates:
        return None

    ranked = rank_image_candidates(
        article,
        candidates
    )

    print(
        "IMAGE CANDIDATES:",
        len(ranked)
    )

    for candidate in ranked[:15]:

        print(
            "IMAGE SCORE:",
            candidate["score"],
            candidate["source_type"],
            candidate["url"][:150]
        )

        downloaded = download_image(
            candidate["url"]
        )

        if not downloaded:
            continue

        content = downloaded["content"]

        h = image_hash(content)

        if h in used_images:
            print(
                "IMAGE ALREADY USED:",
                h[:12]
            )
            continue

        return {
            "content": content,
            "content_type": downloaded[
                "content_type"
            ],
            "hash": h,
            "url": candidate["url"],
            "score": candidate["score"]
        }

    return None


# =========================================================
# TELEGRAM
# =========================================================

def telegram_url(method):
    return (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/{method}"
    )


def send_message(
    text,
    reply_markup=None
):
    payload = {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if reply_markup:
        payload["reply_markup"] = json.dumps(
            reply_markup
        )

    try:

        r = requests.post(
            telegram_url("sendMessage"),
            data=payload,
            timeout=30
        )

        print(
            "SEND MESSAGE:",
            r.status_code,
            r.text[:500]
        )

        return r.ok

    except Exception as e:

        print(
            "SEND MESSAGE ERROR:",
            e
        )

        return False


def send_photo_file(
    image_data,
    caption,
    reply_markup=None
):
    files = {
        "photo": (
            "news.jpg",
            image_data,
            "image/jpeg"
        )
    }

    data = {
        "chat_id": CHANNEL,
        "caption": caption,
        "parse_mode": "HTML"
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(
            reply_markup
        )

    try:

        r = requests.post(
            telegram_url("sendPhoto"),
            data=data,
            files=files,
            timeout=60
        )

        print(
            "SEND PHOTO:",
            r.status_code,
            r.text[:700]
        )

        return r.ok

    except Exception as e:

        print(
            "SEND PHOTO ERROR:",
            e
        )

        return False


# =========================================================
# ВЫБОР НОВОСТЕЙ
# =========================================================

def select_best_articles(
    articles,
    posted
):
    candidates = []

    seen_urls = set()

    for article in articles:

        url = article.get("url")

        if not url:
            continue

        if url in posted:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        age = get_age_hours(
            article.get("date")
        )

        if age > MAX_NEWS_AGE_HOURS:
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

        candidates.append(article)

    candidates.sort(
        key=lambda x: (
            x.get("score", 0),
            -get_age_hours(
                x.get("date")
            )
        ),
        reverse=True
    )

    candidates = remove_similar_news(
        candidates
    )

    return candidates[:MAX_CANDIDATES]


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not configured"
        )

    print("=" * 60)
    print("МРК BUSINESS NEWS BOT v5.1")
    print("=" * 60)

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

    all_articles = []

    # -----------------------------------------------------
    # RSS
    # -----------------------------------------------------

    for feed_name, feed_url in RSS_FEEDS:

        print(
            "\nRSS:",
            feed_name
        )

        xml = get_google_news_rss(
            feed_url
        )

        parsed = parse_rss(
            xml,
            feed_name
        )

        print(
            "Found:",
            len(parsed)
        )

        all_articles.extend(
            parsed
        )

    print(
        "\nTOTAL ARTICLES:",
        len(all_articles)
    )

    # -----------------------------------------------------
    # Отбор
    # -----------------------------------------------------

    selected = select_best_articles(
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

    published_count = 0

    for article in selected:

        if published_count >= MAX_POSTS_PER_RUN:
            break

        print("\n" + "=" * 60)

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
        # Формируем текст
        # -------------------------------------------------

        post_text = format_post(
            article
        )

        keyboard = get_keyboard(
            article
        )

        # -------------------------------------------------
        # Пытаемся найти тематическое фото
        # -------------------------------------------------

        image = find_unique_image(
            article,
            used_images
        )

        success = False

        if image:

            print(
                "SELECTED IMAGE SCORE:",
                image["score"]
            )

            success = send_photo_file(
                image["content"],
                post_text,
                keyboard
            )

            if success:

                used_images.append(
                    image["hash"]
                )

                save_used_images(
                    used_images
                )

                print(
                    "IMAGE SAVED:",
                    image["hash"][:16]
                )

        # -------------------------------------------------
        # Если фото не получилось — текст
        # -------------------------------------------------

        if not success:

            print(
                "Sending text fallback..."
            )

            success = send_message(
                post_text,
                keyboard
            )

        # -------------------------------------------------
        # История
        # -------------------------------------------------

        if success:

            url = article.get("url")

            if url and url not in posted:
                posted.append(url)

            save_posted(posted)

            published_count += 1

            print(
                "PUBLISHED:",
                published_count
            )

            time.sleep(3)

        else:

            print(
                "FAILED TO PUBLISH:"
            )

            print(
                article.get("url")
            )

    print("\n" + "=" * 60)

    print(
        "DONE. Published:",
        published_count
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
