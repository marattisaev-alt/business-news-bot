import os
import json
import requests
import xml.etree.ElementTree as ET

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

RSS_URL = "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en"
POSTED_FILE = "posted.json"


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
        print(f"Не удалось прочитать posted.json: {error}")
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


def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL,
            "text": text,
            "disable_web_page_preview": False
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
        text = (
            "📰 БИЗНЕС НОВОСТИ\n\n"
            f"🔹 {article['title']}\n\n"
            f"🔗 Источник:\n{article['link']}"
        )

        send_message(text)

        posted.add(article["link"])

        print(f"Опубликовано: {article['title']}")

    save_posted(posted)

    print(f"Всего опубликовано: {len(new_posts)}")


if __name__ == "__main__":
    main()
