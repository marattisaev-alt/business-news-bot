import os
import json
import html
import requests
import xml.etree.ElementTree as ET

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
        timeout=20
    )

    response.raise_for_status()

    root = ET.fromstring(response.content)

    news = []

    for item in root.findall(".//item"):
        title = item.findtext("title")
        link = item.findtext("link")

        if title and link:
            news.append({
                "title": title.strip(),
                "link": link.strip()
            })

    return news


def translate_text(text):
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

        translated = data.get("responseData", {}).get(
            "translatedText",
            ""
        )

        if translated:
            return translated.strip()

    except Exception as error:
        print(f"Ошибка перевода: {error}")

    return text


def send_message(title, link):
    safe_title = html.escape(title)

    text = (
        "🏢 <b>БИЗНЕС НОВОСТИ</b>\n\n"
        f"📰 <b>{safe_title}</b>\n\n"
        "🌍 Мировой бизнес и экономика\n\n"
        "📌 Следите за главными событиями рынка "
        "в канале «МРК»."
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
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        },
        timeout=20
    )

    response.raise_for_status()


def main():
    posted = load_posted()
    news = get_news()

    new_posts = []

    for article in news:
        if article["link"] not in posted:
            new_posts.append(article)

    new_posts = new_posts[:3]

    for article in new_posts:
        print(f"Перевод: {article['title']}")

        translated_title = translate_text(article["title"])

        send_message(
            translated_title,
            article["link"]
        )

        posted.add(article["link"])

        print(f"Опубликовано: {translated_title}")

    save_posted(posted)

    print(f"Всего опубликовано: {len(new_posts)}")


if __name__ == "__main__":
    main()
