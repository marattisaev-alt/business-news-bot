import os
import json
import html
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

RSS_URL = "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en"
POSTED_FILE = "posted.json"

TRANSLATE_URL = "https://api.mymemory.translated.net/get"


def load_posted():
    try:
        if not os.path.exists(POSTED_FILE):
            return set()

        with open(POSTED_FILE, "r", encoding="utf-8") as file:
            content = file.read().strip()

        if not content:
            return set()

        data = json.loads(content)

        if not isinstance(data, list):
            return set()

        return set(data)

    except Exception as error:
        print(f"Ошибка posted.json: {error}")
        return set()


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as file:
        json.dump(
            list(posted),
            file,
            ensure_ascii=False,
            indent=2
        )


def get_news():
    response = requests.get(
        RSS_URL,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    root = ET.fromstring(response.content)

    news = []

    for item in root.findall(".//item"):
        title = item.findtext("title")
        link = item.findtext("link")
        description = item.findtext("description")
        source = item.findtext("source")

        if not title or not link:
            continue

        image = None

        for element in item:
            tag = element.tag.lower()

            if "content" in tag or "thumbnail" in tag:
                image = element.attrib.get("url")

                if image:
                    break

        news.append({
            "title": title.strip(),
            "link": link.strip(),
            "description": description or "",
            "source": source or "Источник"
            ,
            "image": image
        })

    return news


def translate_text(text):
    if not text:
        return ""

    try:
        response = requests.get(
            TRANSLATE_URL,
            params={
                "q": text,
                "langpair": "en|ru"
            },
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        translated = data.get(
            "responseData",
            {}
        ).get(
            "translatedText",
            ""
        )

        if translated:
            return translated.strip()

    except Exception as error:
        print(f"Ошибка перевода: {error}")

    return text


def clean_description(text):
    if not text:
        return ""

    # Убираем HTML-теги
    result = ""
    inside_tag = False

    for char in text:
        if char == "<":
            inside_tag = True
            continue

        if char == ">":
            inside_tag = False
            continue

        if not inside_tag:
            result += char

    result = html.unescape(result)

    return " ".join(result.split())


def detect_category(title):
    text = title.lower()

    if any(word in text for word in [
        "apple", "google", "microsoft", "amazon",
        "meta", "tesla", "nvidia", "technology",
        "technology", "software", "ai", "artificial intelligence"
    ]):
        return "💻 Технологии"

    if any(word in text for word in [
        "stock", "stocks", "shares", "investor",
        "investment", "market", "markets", "nasdaq",
        "dow", "s&p", "wall street"
    ]):
        return "📈 Инвестиции"

    if any(word in text for word in [
        "bank", "banks", "interest rate", "inflation",
        "economy", "economic", "fed", "central bank"
    ]):
        return "💰 Экономика"

    if any(word in text for word in [
        "oil", "gas", "energy", "petrol",
        "renewable", "electricity"
    ]):
        return "⚡ Энергетика"

    if any(word in text for word in [
        "startup", "startups", "venture",
        "funding", "founder"
    ]):
        return "🚀 Стартапы"

    return "🏢 Бизнес"


def make_hashtags(category):
    hashtags = {
        "💻 Технологии": "#Технологии #IT",
        "📈 Инвестиции": "#Инвестиции #Рынки",
        "💰 Экономика": "#Экономика #Финансы",
        "⚡ Энергетика": "#Энергетика #Бизнес",
        "🚀 Стартапы": "#Стартапы #Инвестиции",
        "🏢 Бизнес": "#Бизнес #Новости"
    }

    return hashtags.get(
        category,
        "#Бизнес #Новости"
    )


def shorten_text(text, max_length=450):
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    shortened = text[:max_length]

    last_space = shortened.rfind(" ")

    if last_space > 100:
        shortened = shortened[:last_space]

    return shortened + "…"


def build_caption(title, description, source):
    category = detect_category(title)
    hashtags = make_hashtags(category)

    translated_description = translate_text(
        clean_description(description)
    )

    translated_description = shorten_text(
        translated_description
    )

    safe_title = html.escape(title)
    safe_description = html.escape(
        translated_description
    )
    safe_source = html.escape(source)

    text = (
        "🏢 <b>МРК | БИЗНЕС НОВОСТИ</b>\n\n"
        f"📰 <b>{safe_title}</b>\n\n"
        f"{category}\n\n"
    )

    if safe_description:
        text += (
            "📌 <b>Коротко:</b>\n"
            f"{safe_description}\n\n"
        )

    text += (
        f"🗞 <b>Источник:</b> {safe_source}\n\n"
        f"{hashtags}"
    )

    return text


def send_text(title, description, source, link):
    caption = build_caption(
        title,
        description,
        source
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

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        },
        timeout=20
    )

    response.raise_for_status()


def send_photo(
    title,
    description,
    source,
    link,
    image
):
    caption = build_caption(
        title,
        description,
        source
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

    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL,
            "photo": image,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        },
        timeout=30
    )

    response.raise_for_status()


def main():
    posted = load_posted()
    news = get_news()

    new_posts = []

    for article in news:
        if article["link"] not in posted:
            new_posts.append(article)

    # Максимум 3 новости за один запуск
    new_posts = new_posts[:3]

    for article in new_posts:

        print(
            f"Обрабатываем: "
            f"{article['title']}"
        )

        translated_title = translate_text(
            article["title"]
        )

        try:
            if article["image"]:

                send_photo(
                    translated_title,
                    article["description"],
                    article["source"],
                    article["link"],
                    article["image"]
                )

                print(
                    "Опубликовано с изображением"
                )

            else:

                send_text(
                    translated_title,
                    article["description"],
                    article["source"],
                    article["link"]
                )

                print(
                    "Опубликовано без изображения"
                )

        except Exception as error:

            print(
                f"Ошибка публикации с фото: "
                f"{error}"
            )

            send_text(
                translated_title,
                article["description"],
                article["source"],
                article["link"]
            )

        posted.add(article["link"])

        print(
            f"Опубликовано: "
            f"{translated_title}"
        )

    save_posted(posted)

    print(
        f"Всего опубликовано: "
        f"{len(new_posts)}"
    )


if __name__ == "__main__":
    main()
