import os
import json
import html
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

POSTED_FILE = "posted.json"

MAX_POSTS_PER_RUN = 2
MIN_SCORE = 6


FEEDS = [
    {
        "name": "Reuters",
        "query": "site:reuters.com/business",
        "bonus": 3
    },

    {
        "name": "Бизнес",
        "query": "business",
        "bonus": 1
    },

    {
        "name": "Рынки",
        "query": "stock market OR investing OR IPO",
        "bonus": 2
    },

    {
        "name": "Экономика",
        "query": "economy OR inflation OR interest rates",
        "bonus": 2
    },

    {
        "name": "Технологии",
        "query": "\"artificial intelligence\" OR technology OR chips",
        "bonus": 2
    },

    {
        "name": "США",
        "query": "United States business OR US economy OR American companies",
        "bonus": 3
    },

    {
        "name": "Россия",
        "query": "Russia business OR Russia economy OR Russian companies",
        "bonus": 3
    }
]


def load_posted():
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

            if isinstance(data, list):
                return set(data)

    except Exception:
        pass

    return set()


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(
            list(posted)[-1000:],
            f,
            ensure_ascii=False,
            indent=2
        )


def translate_to_russian(text):
    if not text:
        return ""

    try:
        url = "https://api.mymemory.translated.net/get"

        response = requests.get(
            url,
            params={
                "q": text,
                "langpair": "en|ru"
            },
            timeout=10
        )

        data = response.json()

        translated = data.get("responseData", {}).get(
            "translatedText",
            ""
        )

        if translated:
            return translated

    except Exception:
        pass

    return text


def clean_html(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)

    text = html.unescape(text)

    return text.strip()


def calculate_score(title, description, bonus):
    text = f"{title} {description}".lower()

    score = 3

    major_companies = [
        "apple",
        "microsoft",
        "google",
        "alphabet",
        "amazon",
        "meta",
        "nvidia",
        "tesla",
        "openai",
        "anthropic",
        "intel",
        "samsung",
        "tiktok",
        "uber",
        "netflix",
        "boeing",
        "coca-cola",
        "pepsi",
        "walmart",
        "visa",
        "mastercard",
        "goldman sachs",
        "jpmorgan",
        "morgan stanley"
    ]

    critical_words = [
        "breaking",
        "urgent",
        "crisis",
        "collapse",
        "bankruptcy",
        "acquisition",
        "merger",
        "deal",
        "sanctions",
        "tariff",
        "tariffs",
        "layoffs",
        "investigation",
        "lawsuit",
        "record",
        "surge",
        "plunge"
    ]

    finance_words = [
        "stocks",
        "shares",
        "market",
        "markets",
        "investor",
        "investors",
        "investment",
        "ipo",
        "profit",
        "revenue",
        "earnings",
        "inflation",
        "interest rate",
        "central bank",
        "fed",
        "ecb"
    ]

    money_words = [
        "million",
        "billion",
        "trillion",
        "dollar",
        "dollars",
        "euro",
        "euros",
        "rubles",
        "руб",
        "млрд",
        "млн"
    ]

    technology_words = [
        "artificial intelligence",
        "ai",
        "technology",
        "chip",
        "chips",
        "semiconductor",
        "software",
        "robot",
        "robotics"
    ]

    usa_words = [
        "united states",
        "u.s.",
        "american",
        "washington",
        "new york",
        "california",
        "silicon valley"
    ]

    russia_words = [
        "russia",
        "russian",
        "moscow",
        "rubles",
        "ruble"
    ]

    for word in major_companies:
        if word in text:
            score += 2

    for word in critical_words:
        if word in text:
            score += 2

    for word in finance_words:
        if word in text:
            score += 1

    for word in money_words:
        if word in text:
            score += 1

    for word in technology_words:
        if word in text:
            score += 1

    for word in usa_words:
        if word in text:
            score += 1

    for word in russia_words:
        if word in text:
            score += 1

    score += bonus

    return min(score, 10)


def detect_category(title, description):
    text = f"{title} {description}".lower()

    # Сначала определяем США и Россию,
    # чтобы региональные новости не уходили
    # автоматически в другие категории.

    if any(
        word in text
        for word in [
            "united states",
            "u.s.",
            "american",
            "washington",
            "new york",
            "california"
        ]
    ):
        return "🇺🇸 США"

    if any(
        word in text
        for word in [
            "russia",
            "russian",
            "moscow",
            "rubles",
            "ruble"
        ]
    ):
        return "🇷🇺 Россия"

    if any(
        word in text
        for word in [
            "artificial intelligence",
            "technology",
            "chip",
            "chips",
            "semiconductor",
            "software",
            "robotics"
        ]
    ):
        return "🤖 Технологии"

    if any(
        word in text
        for word in [
            "stock",
            "stocks",
            "shares",
            "market",
            "investor",
            "investors",
            "ipo",
            "investment"
        ]
    ):
        return "📈 Рынки"

    if any(
        word in text
        for word in [
            "inflation",
            "interest rate",
            "central bank",
            "economy",
            "economic",
            "gdp"
        ]
    ):
        return "💰 Экономика"

    if any(
        word in text
        for word in [
            "business",
            "company",
            "corporation",
            "revenue",
            "profit",
            "earnings"
        ]
    ):
        return "🏢 Бизнес"

    return "📰 Новости"


def make_hashtags(category):
    hashtags = {
        "🇺🇸 США":
            "#США #Бизнес",

        "🇷🇺 Россия":
            "#Россия #Бизнес",

        "🤖 Технологии":
            "#Технологии #AI",

        "📈 Рынки":
            "#Рынки #Инвестиции",

        "💰 Экономика":
            "#Экономика",

        "🏢 Бизнес":
            "#Бизнес",

        "📰 Новости":
            "#Новости"
    }

    return hashtags.get(category, "#Новости")


def parse_date(date_string):
    if not date_string:
        return ""

    try:
        dt = parsedate_to_datetime(date_string)

        return dt.strftime("%d.%m.%Y %H:%M")

    except Exception:
        return ""


def get_google_news_rss(query):
    url = "https://news.google.com/rss/search"

    params = {
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        return response.text

    except Exception as e:
        print("RSS error:", e)

        return ""


def parse_rss(xml_text, source_name, bonus):
    if not xml_text:
        return []

    items = []

    try:
        root = ET.fromstring(xml_text)

        for item in root.findall(".//item"):
            title_element = item.find("title")
            link_element = item.find("link")
            description_element = item.find("description")
            date_element = item.find("pubDate")

            title = (
                title_element.text
                if title_element is not None
                else ""
            )

            link = (
                link_element.text
                if link_element is not None
                else ""
            )

            description = (
                description_element.text
                if description_element is not None
                else ""
            )

            pub_date = (
                date_element.text
                if date_element is not None
                else ""
            )

            title = clean_html(title)
            description = clean_html(description)

            if not title or not link:
                continue

            score = calculate_score(
                title,
                description,
                bonus
            )

            category = detect_category(
                title,
                description
            )

            hashtags = make_hashtags(category)

            items.append({
                "title": title,
                "description": description,
                "link": link,
                "source": source_name,
                "date": parse_date(pub_date),
                "score": score,
                "category": category,
                "hashtags": hashtags
            })

    except Exception as e:
        print("RSS parsing error:", e)

    return items


def send_message(text, link):
    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🔗 Читать источник",
                    "url": link
                }
            ]
        ]
    }

    payload = {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "reply_markup": json.dumps(keyboard)
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=20
        )

        print("Telegram:", response.status_code)

        if response.ok:
            return True

        print(response.text)

    except Exception as e:
        print("Telegram error:", e)

    return False


def format_post(item):
    title_ru = translate_to_russian(
        item["title"]
    )

    description_ru = translate_to_russian(
        item["description"]
    )

    title_ru = html.escape(
        title_ru.strip()
    )

    description_ru = html.escape(
        description_ru.strip()
    )

    if len(description_ru) > 500:
        description_ru = (
            description_ru[:500].rsplit(" ", 1)[0]
            + "..."
        )

    category = html.escape(
        item["category"]
    )

    hashtags = item["hashtags"]

    date_text = item["date"]

    post = (
        f"<b>{category}</b>\n\n"
        f"<b>{title_ru}</b>\n"
    )

    if description_ru:
        post += f"\n{description_ru}\n"

    if date_text:
        post += f"\n🕒 {date_text}\n"

    post += (
        f"\n📊 Важность: "
        f"<b>{item['score']}/10</b>\n"
        f"\n{hashtags}"
    )

    return post


def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing")
        return

    if not CHANNEL:
        print("ERROR: CHANNEL is missing")
        return

    posted = load_posted()

    all_news = []

    print("Получаем новости...")

    for feed in FEEDS:
        print(
            f"Источник: {feed['name']}"
        )

        xml_text = get_google_news_rss(
            feed["query"]
        )

        news = parse_rss(
            xml_text,
            feed["name"],
            feed["bonus"]
        )

        all_news.extend(news)

    print(
        f"Всего найдено: {len(all_news)}"
    )

    # Убираем дубликаты
    unique_news = []
    seen_links = set()

    for item in all_news:
        if item["link"] in seen_links:
            continue

        seen_links.add(item["link"])

        if item["link"] in posted:
            continue

        unique_news.append(item)

    # Сначала самые важные новости
    unique_news.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    published = 0

    for item in unique_news:

        if item["score"] < MIN_SCORE:
            continue

        if published >= MAX_POSTS_PER_RUN:
            break

        text = format_post(item)

        print(
            f"Публикуем: "
            f"{item['title']} "
            f"({item['score']}/10)"
        )

        success = send_message(
            text,
            item["link"]
        )

        if success:
            posted.add(item["link"])
            published += 1

    save_posted(posted)

    print(
        f"Готово. Опубликовано: {published}"
    )


if __name__ == "__main__":
    main()
