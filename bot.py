import os
import requests
import xml.etree.ElementTree as ET

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

RSS_URL = "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en"

def get_news():
    response = requests.get(RSS_URL, timeout=20)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    news = []

    for item in root.findall(".//item")[:5]:
        title = item.findtext("title")
        link = item.findtext("link")

        if title and link:
            news.append({
                "title": title,
                "link": link
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


news = get_news()

if news:
    article = news[0]

    text = (
        "📰 БИЗНЕС НОВОСТИ\n\n"
        f"🔹 {article['title']}\n\n"
        f"🔗 Читать источник:\n{article['link']}"
    )

    send_message(text)

    print("Новость опубликована:", article["title"])
else:
    print("Новых новостей не найдено")
