import os
import re
import json
import html
import hashlib
import tempfile
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests
import xml.etree.ElementTree as ET


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = os.environ.get("CHANNEL", "@etomrk")

MAX_POSTS_PER_RUN = 2
MIN_SCORE = 7
MAX_CANDIDATES = 60

# Не брать новости старше этого количества часов
MAX_NEWS_AGE_HOURS = 48

# Максимальный размер изображения
MAX_IMAGE_SIZE = 9 * 1024 * 1024

POSTED_FILE = "posted.json"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================================================
# RSS ЛЕНТЫ
# =========================================================

FEEDS = [
    (
        "Reuters",
        "https://news.google.com/rss/search?q=Reuters+business+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "USA",
        "https://news.google.com/rss/search?q=USA+business+economy+companies+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Russia",
        "https://news.google.com/rss/search?q=Russia+business+economy+companies+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Markets",
        "https://news.google.com/rss/search?q=stock+market+markets+investors+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Economy",
        "https://news.google.com/rss/search?q=economy+inflation+GDP+rates+central+bank+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Technology",
        "https://news.google.com/rss/search?q=technology+AI+chips+Microsoft+Apple+Google+Nvidia+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
    (
        "Business",
        "https://news.google.com/rss/search?q=business+companies+investment+acquisition+deal+when:2d&hl=en-US&gl=US&ceid=US:en"
    ),
]


# =========================================================
# КЛЮЧЕВЫЕ СЛОВА
# =========================================================

COMPANY_WORDS = [
    "apple", "microsoft", "google", "alphabet", "amazon", "meta",
    "nvidia", "tesla", "openai", "samsung", "intel", "oracle",
    "berkshire", "jpmorgan", "goldman", "visa", "mastercard",
    "netflix", "uber", "boeing", "airbus", "toyota",
    "gazprom", "rosneft", "sberbank", "sber", "yandex",
    "lukoil", "novatek", "vtb", "alrosa", "ozon", "wildberries"
]

CRITICAL_WORDS = [
    "crisis", "collapse", "bankruptcy", "default", "sanctions",
    "war", "tariff", "emergency", "ban", "shutdown",
    "recall", "investigation", "fraud", "lawsuit"
]

FINANCE_WORDS = [
    "market", "stocks", "shares", "investors", "investment",
    "bank", "banks", "rate", "rates", "interest", "inflation",
    "recession", "gdp", "economy", "currency", "ruble",
    "dollar", "euro", "bond", "bonds"
]

MONEY_WORDS = [
    "billion", "million", "trillion", "investment",
    "acquisition", "merger", "deal", "funding",
    "revenue", "profit", "loss", "earnings",
    "valuation", "contract"
]

TECH_WORDS = [
    "ai", "artificial intelligence", "chip", "chips",
    "semiconductor", "software", "cloud", "data center",
    "robot", "robotics", "technology", "cyber"
]

USA_WORDS = [
    "usa", "u.s.", "united states", "america",
    "american", "washington", "new york", "california"
]

RUSSIA_WORDS = [
    "russia", "russian", "moscow", "kremlin",
    "rubles", "ruble", "россия", "москва"
]

MARKET_MOVE_WORDS = [
    "surged", "jumped", "rallied", "rose", "gained",
    "fell", "dropped", "plunged", "slumped",
    "soared", "tumbled", "record high", "record low"
]

MACRO_WORDS = [
    "inflation", "gdp", "interest rate", "central bank",
    "fed", "federal reserve", "ecb", "oil prices",
    "unemployment", "recession", "economic growth"
]

CLICKBAIT_WORDS = [
    "you won't believe",
    "shocking",
    "secret",
    "this changes everything",
    "must see",
    "unbelievable",
    "click",
    "viral"
]

LOW_VALUE_WORDS = [
    "celebrity", "entertainment", "movie",
    "music", "sports", "football", "soccer",
    "weather forecast"
]


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()

    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\w\s%$€₽-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def shorten_title(title, max_length=150):
    """
    Делаем заголовок компактнее для Telegram,
    не придумывая новые факты.
    """

    title = clean_text(title)

    # Убираем типичные хвосты Google News
    title = re.sub(
        r"\s+[|–—-]\s+(Reuters|CNBC|Bloomberg|BBC|Forbes|CNN|AP News)\s*$",
        "",
        title,
        flags=re.I
    )

    title = title.strip()

    if len(title) <= max_length:
        return title

    shortened = title[:max_length]

    # Не обрезаем посередине слова
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]

    return shortened + "…"


def escape_html(text):
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def load_posted():
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

        return set()

    except Exception:
        return set()


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(
            sorted(list(posted)),
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# ДАТА
# =========================================================

def parse_date(date_string):
    if not date_string:
        return None

    try:
        dt = parsedate_to_datetime(date_string)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def get_age_hours(dt):
    if not dt:
        return None

    now = datetime.now(timezone.utc)

    return (now - dt).total_seconds() / 3600


# =========================================================
# RSS
# =========================================================

def get_google_news_rss(source_name, url):
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; MRKBusinessBot/4.0)"
                )
            }
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        return parse_rss(root, source_name)

    except Exception as e:
        print(f"RSS error [{source_name}]: {e}")
        return []


def parse_rss(root, source_name):
    articles = []

    namespaces = {
        "media": "http://search.yahoo.com/mrss/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/"
    }

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

        source_element = item.find("source")

        source = source_name

        if source_element is not None:
            source_text = clean_text(source_element.text or "")
            if source_text:
                source = source_text

        image_url = None

        # media:content
        media_content = item.find(
            "media:content",
            namespaces
        )

        if media_content is not None:
            image_url = (
                media_content.attrib.get("url")
                or media_content.attrib.get("href")
            )

        # media:thumbnail
        if not image_url:
            media_thumbnail = item.find(
                "media:thumbnail",
                namespaces
            )

            if media_thumbnail is not None:
                image_url = (
                    media_thumbnail.attrib.get("url")
                    or media_thumbnail.attrib.get("href")
                )

        # enclosure
        if not image_url:
            enclosure = item.find("enclosure")

            if enclosure is not None:
                enc_type = enclosure.attrib.get("type", "")

                if enc_type.startswith("image/"):
                    image_url = enclosure.attrib.get("url")

        if not title or not link:
            continue

        articles.append({
            "title": title,
            "description": description,
            "link": link,
            "date": parse_date(pub_date),
            "source": source,
            "rss_image": image_url,
        })

    return articles


# =========================================================
# КАТЕГОРИЯ
# =========================================================

def detect_category(article):
    text = normalize(
        article["title"] + " " +
        article["description"]
    )

    if any(word in text for word in RUSSIA_WORDS):
        return "🇷🇺 Россия"

    if any(word in text for word in USA_WORDS):
        return "🇺🇸 США"

    if any(word in text for word in TECH_WORDS):
        return "💻 Технологии"

    if any(word in text for word in MACRO_WORDS):
        return "📈 Экономика"

    if any(word in text for word in MARKET_MOVE_WORDS):
        return "💰 Рынки"

    if any(word in text for word in FINANCE_WORDS):
        return "💰 Финансы"

    if any(word in text for word in MONEY_WORDS):
        return "🏢 Бизнес"

    return "📰 Деловые новости"


# =========================================================
# РЕЙТИНГ
# =========================================================

def calculate_score(article):
    title = normalize(article["title"])
    description = normalize(article["description"])

    text = title + " " + description

    score = 5.0

    # -----------------------------------------------------
    # Сильные компании
    # -----------------------------------------------------

    company_hits = sum(
        1 for word in COMPANY_WORDS
        if word in text
    )

    score += min(company_hits * 1.2, 3.0)

    # -----------------------------------------------------
    # Критические события
    # -----------------------------------------------------

    critical_hits = sum(
        1 for word in CRITICAL_WORDS
        if word in text
    )

    score += min(critical_hits * 1.5, 4.0)

    # -----------------------------------------------------
    # Финансы
    # -----------------------------------------------------

    finance_hits = sum(
        1 for word in FINANCE_WORDS
        if word in text
    )

    score += min(finance_hits * 0.4, 2.5)

    # -----------------------------------------------------
    # Деньги / сделки
    # -----------------------------------------------------

    money_hits = sum(
        1 for word in MONEY_WORDS
        if word in text
    )

    score += min(money_hits * 0.7, 3.0)

    # -----------------------------------------------------
    # Технологии
    # -----------------------------------------------------

    tech_hits = sum(
        1 for word in TECH_WORDS
        if word in text
    )

    score += min(tech_hits * 0.5, 2.0)

    # -----------------------------------------------------
    # Макроэкономика
    # -----------------------------------------------------

    macro_hits = sum(
        1 for word in MACRO_WORDS
        if word in text
    )

    score += min(macro_hits * 0.8, 2.5)

    # -----------------------------------------------------
    # Движение рынка
    # -----------------------------------------------------

    market_hits = sum(
        1 for word in MARKET_MOVE_WORDS
        if word in text
    )

    score += min(market_hits * 0.8, 2.5)

    # -----------------------------------------------------
    # Крупные суммы
    # -----------------------------------------------------

    if re.search(
        r"\$?\d+(?:[.,]\d+)?\s*(billion|bn|trillion|tn)",
        text
    ):
        score += 2.5

    if re.search(
        r"\d+(?:[.,]\d+)?\s*%",
        text
    ):
        score += 1.0

    # -----------------------------------------------------
    # Срочность
    # -----------------------------------------------------

    urgency_words = [
        "breaking",
        "urgent",
        "just announced",
        "today",
        "now",
        "immediately"
    ]

    urgency_hits = sum(
        1 for word in urgency_words
        if word in text
    )

    score += min(urgency_hits * 0.8, 2.0)

    # -----------------------------------------------------
    # Источник
    # -----------------------------------------------------

    source = article["source"].lower()

    if "reuters" in source:
        score += 2.5

    elif "bloomberg" in source:
        score += 2.0

    elif "cnbc" in source:
        score += 1.5

    elif "financial times" in source:
        score += 1.5

    # -----------------------------------------------------
    # Свежесть
    # -----------------------------------------------------

    age = get_age_hours(article["date"])

    if age is not None:

        if age <= 6:
            score += 2.0

        elif age <= 24:
            score += 1.0

        elif age <= 48:
            score += 0

        else:
            score -= 4.0

    # -----------------------------------------------------
    # Штраф за низкую ценность
    # -----------------------------------------------------

    low_value_hits = sum(
        1 for word in LOW_VALUE_WORDS
        if word in text
    )

    score -= min(low_value_hits * 1.5, 4.0)

    return round(max(score, 0), 1)


# =========================================================
# АНТИ-КЛИКБЕЙТ
# =========================================================

def clickbait_penalty(article):
    text = normalize(article["title"])

    penalty = 0

    for word in CLICKBAIT_WORDS:
        if word in text:
            penalty += 1

    if "?" in article["title"]:
        penalty += 0.5

    return penalty


# =========================================================
# ДУБЛИКАТЫ
# =========================================================

def important_words(text):
    words = normalize(text).split()

    stopwords = {
        "the", "a", "an", "and", "or", "of",
        "to", "in", "on", "for", "with",
        "from", "by", "as", "at", "is",
        "are", "was", "were", "this",
        "that", "new", "after", "before"
    }

    result = []

    for word in words:
        if len(word) >= 4 and word not in stopwords:
            result.append(word)

    return set(result)


def similarity(title1, title2):
    a = important_words(title1)
    b = important_words(title2)

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
                article["title"],
                existing["title"]
            )

            if sim >= 0.50:
                duplicate = True

                # Оставляем более высокий рейтинг
                if article["score"] > existing["score"]:
                    result.remove(existing)
                    duplicate = False

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

    # Если уже преимущественно кириллица
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text))
    latin = len(re.findall(r"[A-Za-z]", text))

    if cyrillic > latin:
        return text

    try:

        url = (
            "https://api.mymemory.translated.net/get"
            "?q=" + quote(text[:4500])
            + "&langpair=en|ru"
        )

        response = requests.get(
            url,
            timeout=15
        )

        data = response.json()

        translated = (
            data.get("responseData", {})
                .get("translatedText", "")
        )

        if translated:
            return clean_text(translated)

    except Exception as e:
        print("Translation error:", e)

    return text


# =========================================================
# АНАЛИТИКА МРК
# =========================================================

def generate_analysis(article):
    text = normalize(
        article["title"] + " " +
        article["description"]
    )

    company = any(
        word in text for word in COMPANY_WORDS
    )

    money = any(
        word in text for word in MONEY_WORDS
    )

    market = any(
        word in text for word in MARKET_MOVE_WORDS
    )

    macro = any(
        word in text for word in MACRO_WORDS
    )

    tech = any(
        word in text for word in TECH_WORDS
    )

    critical = any(
        word in text for word in CRITICAL_WORDS
    )

    if critical and market:
        return (
            "Событие может оказать заметное влияние на рыночные "
            "настроения. Инвесторы, вероятно, будут оценивать "
            "риски для компаний и активов, связанных с этой историей."
        )

    if money:
        return (
            "Ключевой фактор — финансовый масштаб события. "
            "Крупные сделки, инвестиции и изменения прибыли могут "
            "влиять на оценку компании и ожидания инвесторов."
        )

    if market:
        return (
            "Главное значение новости — возможная реакция рынка. "
            "Изменение ожиданий инвесторов может отразиться на "
            "котировках компаний и связанных активов."
        )

    if macro:
        return (
            "Новость важна для экономики в целом: изменение ставок, "
            "инфляции или экономического роста может повлиять на "
            "стоимость денег, потребительский спрос и инвестиции."
        )

    if tech:
        return (
            "Событие имеет значение для технологического сектора. "
            "Оно может повлиять на конкуренцию, инвестиции и "
            "дальнейшее развитие соответствующего рынка."
        )

    if company:
        return (
            "Для бизнеса это важно из-за возможного влияния на "
            "стратегию компании, её финансовые показатели и "
            "позицию на рынке."
        )

    return (
        "Новость представляет интерес для деловой аудитории, "
        "поскольку может повлиять на бизнес-среду, рынки или "
        "экономические ожидания."
    )


# =========================================================
# ХЭШТЕГИ
# =========================================================

def generate_hashtags(article):
    text = normalize(
        article["title"] + " " +
        article["description"]
    )

    tags = ["#МРК", "#БизнесНовости"]

    if any(word in text for word in USA_WORDS):
        tags.append("#США")

    if any(word in text for word in RUSSIA_WORDS):
        tags.append("#Россия")

    if any(word in text for word in TECH_WORDS):
        tags.append("#Технологии")

    if any(word in text for word in MACRO_WORDS):
        tags.append("#Экономика")

    if any(word in text for word in MARKET_MOVE_WORDS):
        tags.append("#Рынки")

    if any(word in text for word in MONEY_WORDS):
        tags.append("#Бизнес")

    return " ".join(dict.fromkeys(tags))


# =========================================================
# ФОРМАТ ПОСТА
# =========================================================

def format_post(article):
    category = article["category"]

    title_ru = shorten_title(
        translate_text(article["title"]),
        180
    )

    description_ru = translate_text(
        article["description"]
    )

    if len(description_ru) > 500:
        description_ru = description_ru[:500].rsplit(" ", 1)[0] + "…"

    analysis = generate_analysis(article)

    source = escape_html(article["source"])
    title_ru = escape_html(title_ru)
    description_ru = escape_html(description_ru)
    analysis = escape_html(analysis)

    date_text = ""

    if article["date"]:
        local_date = article["date"].astimezone()
        date_text = local_date.strftime(
            "%d.%m.%Y %H:%M"
        )

    hashtags = generate_hashtags(article)

    text = (
        f"<b>{category}</b>\n\n"
        f"<b>{title_ru}</b>\n\n"
    )

    if description_ru:
        text += f"{description_ru}\n\n"

    text += (
        f"📊 <b>Почему это важно</b>\n"
        f"{analysis}\n\n"
        f"⭐ <b>Важность:</b> {article['score']}/10\n"
    )

    if date_text:
        text += f"🕐 <b>Дата:</b> {date_text}\n"

    text += (
        f"📰 <b>Источник:</b> {source}\n\n"
        f"{hashtags}"
    )

    # Telegram caption limit — держим запас
    if len(text) > 1000:
        text = text[:995] + "…"

    return text


# =========================================================
# КНОПКА ИСТОЧНИКА
# =========================================================

def get_keyboard(url):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📰 Читать источник",
                    "url": url
                }
            ]
        ]
    }


# =========================================================
# ИЗОБРАЖЕНИЕ С САЙТА
# =========================================================

def get_article_image(article_url):
    try:

        response = requests.get(
            article_url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
                )
            },
            allow_redirects=True
        )

        if response.status_code != 200:
            return None

        page = response.text

        # og:image
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            page,
            re.I
        )

        if match:
            return html.unescape(match.group(1))

        # Обратный порядок атрибутов
        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
            page,
            re.I
        )

        if match:
            return html.unescape(match.group(1))

        # twitter:image
        match = re.search(
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
            page,
            re.I
        )

        if match:
            return html.unescape(match.group(1))

        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image',
            page,
            re.I
        )

        if match:
            return html.unescape(match.group(1))

    except Exception as e:
        print("Article image error:", e)

    return None


# =========================================================
# СКАЧИВАНИЕ ИЗОБРАЖЕНИЯ
# =========================================================

def download_image(image_url):
    if not image_url:
        return None

    try:

        response = requests.get(
            image_url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            stream=True,
            allow_redirects=True
        )

        if response.status_code != 200:
            return None

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        # Нам нужны нормальные изображения
        if not any(
            x in content_type
            for x in [
                "image/jpeg",
                "image/jpg",
                "image/png"
            ]
        ):
            return None

        content_length = response.headers.get(
            "Content-Length"
        )

        if content_length:
            try:
                if int(content_length) > MAX_IMAGE_SIZE:
                    return None
            except Exception:
                pass

        extension = ".jpg"

        if "png" in content_type:
            extension = ".png"

        filename = os.path.join(
            tempfile.gettempdir(),
            "mrk_news" + extension
        )

        total = 0

        with open(filename, "wb") as f:

            for chunk in response.iter_content(
                chunk_size=8192
            ):

                if not chunk:
                    continue

                total += len(chunk)

                if total > MAX_IMAGE_SIZE:
                    f.close()

                    try:
                        os.remove(filename)
                    except Exception:
                        pass

                    return None

                f.write(chunk)

        if total < 1000:
            try:
                os.remove(filename)
            except Exception:
                pass

            return None

        return filename

    except Exception as e:
        print("Download image error:", e)

        return None


# =========================================================
# ПОИСК ЛУЧШЕЙ ФОТОГРАФИИ
# =========================================================

def find_image(article):
    candidates = []

    # 1. Картинка прямо из RSS
    if article.get("rss_image"):
        candidates.append(
            article["rss_image"]
        )

    # 2. og:image / twitter:image
    page_image = get_article_image(
        article["link"]
    )

    if page_image:
        candidates.append(page_image)

    # Убираем дубли
    unique = []

    for url in candidates:
        if url and url not in unique:
            unique.append(url)

    for url in unique:

        filename = download_image(url)

        if filename:
            print("Image found:", url)
            return filename

    print("No usable image:", article["title"])

    return None


# =========================================================
# TELEGRAM
# =========================================================

def send_message(text, url):
    endpoint = f"{TELEGRAM_API}/sendMessage"

    data = {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(
            get_keyboard(url)
        ),
        "disable_web_page_preview": False
    }

    response = requests.post(
        endpoint,
        data=data,
        timeout=30
    )

    print("sendMessage:", response.status_code)

    return response.json()


def send_photo_file(filename, caption, url):
    endpoint = f"{TELEGRAM_API}/sendPhoto"

    try:

        with open(filename, "rb") as photo:

            files = {
                "photo": photo
            }

            data = {
                "chat_id": CHANNEL,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(
                    get_keyboard(url)
                )
            }

            response = requests.post(
                endpoint,
                data=data,
                files=files,
                timeout=60
            )

        print("sendPhoto:", response.status_code)

        return response.json()

    except Exception as e:

        print("sendPhoto exception:", e)

        return {
            "ok": False,
            "description": str(e)
        }


# =========================================================
# ФИНАЛЬНЫЙ ОТБОР
# =========================================================

def select_best_articles(articles):
    # Сначала сортировка по рейтингу
    articles.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    selected = []

    categories_used = set()

    # Первый проход:
    # стараемся не публиковать подряд одинаковые категории

    for article in articles:

        if len(selected) >= MAX_POSTS_PER_RUN:
            break

        category = article["category"]

        if category not in categories_used:
            selected.append(article)
            categories_used.add(category)

    # Если ничего не нашли — добираем лучшие
    if len(selected) < MAX_POSTS_PER_RUN:

        for article in articles:

            if len(selected) >= MAX_POSTS_PER_RUN:
                break

            if article not in selected:
                selected.append(article)

    return selected


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return

    print("======================================")
    print("МРК BUSINESS NEWS BOT 4.0")
    print("======================================")

    posted = load_posted()

    all_articles = []

    # -----------------------------------------------------
    # Получаем новости
    # -----------------------------------------------------

    for source_name, feed_url in FEEDS:

        print("Loading:", source_name)

        articles = get_google_news_rss(
            source_name,
            feed_url
        )

        all_articles.extend(articles)

    print(
        "Total RSS articles:",
        len(all_articles)
    )

    # -----------------------------------------------------
    # Первичная обработка
    # -----------------------------------------------------

    candidates = []

    for article in all_articles:

        if article["link"] in posted:
            continue

        age = get_age_hours(
            article["date"]
        )

        # Старые новости отбрасываем
        if age is not None and age > MAX_NEWS_AGE_HOURS:
            continue

        article["category"] = detect_category(
            article
        )

        article["score"] = calculate_score(
            article
        )

        article["score"] -= clickbait_penalty(
            article
        )

        article["score"] = round(
            max(article["score"], 0),
            1
        )

        if article["score"] < MIN_SCORE:
            continue

        candidates.append(article)

    print(
        "Candidates after filtering:",
        len(candidates)
    )

    # -----------------------------------------------------
    # Убираем похожие новости
    # -----------------------------------------------------

    candidates = remove_similar_news(
        candidates
    )

    # -----------------------------------------------------
    # Максимум кандидатов
    # -----------------------------------------------------

    candidates = sorted(
        candidates,
        key=lambda x: x["score"],
        reverse=True
    )[:MAX_CANDIDATES]

    # -----------------------------------------------------
    # Выбираем лучшие
    # -----------------------------------------------------

    selected = select_best_articles(
        candidates
    )

    print(
        "Selected:",
        len(selected)
    )

    # -----------------------------------------------------
    # Публикация
    # -----------------------------------------------------

    for article in selected:

        print()
        print("--------------------------------------")
        print("Publishing:", article["title"])
        print("Category:", article["category"])
        print("Score:", article["score"])
        print("Source:", article["source"])

        caption = format_post(
            article
        )

        image_file = None

        try:

            # Ищем фотографию
            image_file = find_image(
                article
            )

            # -------------------------------------------------
            # Сначала пробуем фото
            # -------------------------------------------------

            if image_file:

                result = send_photo_file(
                    image_file,
                    caption,
                    article["link"]
                )

                # Если Telegram не принял фото —
                # отправляем обычный текст
                if not result.get("ok"):

                    print(
                        "Photo failed. "
                        "Sending text instead."
                    )

                    send_message(
                        caption,
                        article["link"]
                    )

            else:

                send_message(
                    caption,
                    article["link"]
                )

            # Добавляем URL в историю
            posted.add(
                article["link"]
            )

        except Exception as e:

            print(
                "Publishing error:",
                e
            )

        finally:

            if image_file:

                try:
                    os.remove(
                        image_file
                    )
                except Exception:
                    pass

    # -----------------------------------------------------
    # Сохраняем историю
    # -----------------------------------------------------

    save_posted(posted)

    print()
    print("======================================")
    print("BOT FINISHED")
    print("Posted total:", len(posted))
    print("======================================")


if __name__ == "__main__":
    main()
