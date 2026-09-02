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

        if not title or not link:
            continue

        image = None

        # Попытка найти изображение в RSS
        for element in item:
            tag = element.tag.lower()

            if "content" in tag or "thumbnail" in tag:
                url = element.attrib.get("url")

                if url:
                    image = url
                    break

        news.append({
            "title": title.strip(),
            "link": link.strip(),
            "image": image
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


def make_hashtags(title):
    title_lower = title.lower()

    tags = ["#Бизнес"]

    if any(word in title_lower for word in [
        "банк", "банков", "ставк", "инфляц", "эконом"
    ]):
        tags.append("#Экономика")

    if any(word in title_lower for word in [
        "apple", "google", "microsoft", "ai",
        "искусственн", "технолог", "software"
    ]):
        tags.append("#Технологии")

    if any(word in title_lower for word in [
        "stock", "акци", "рынок", "инвест", "бирж"
    ]):
        tags.append("#Инвестиции")

    return " ".join(tags[:3])


def build_caption(title):
    safe_title = html.escape(title)
    hashtags = make_hashtags(title)

    return (
        "🏢 <b>БИЗНЕС НОВОСТИ</b>\n\n"
        f"📰 <b>{safe_title}</b>\n\n"
        "🌍 Мировой бизнес и экономика\n\n"
        f"{hashtags}"
    )


def send_text(title, link):
    caption = build_caption(title)

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


def send_photo(title, link, image):
    caption = build_caption(title)

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

    # Не больше 3 новостей за один запуск
    new_posts = new_posts[:3]

    for article in new_posts:

        print(f"Обрабатываем: {article['title']}")

        translated_title = translate_text(
            article["title"]
        )

        try:
            if article["image"]:
                send_photo(
                    translated_title,
                    article["link"],
                    article["image"]
                )

                print("Опубликовано с изображением")

            else:
                send_text(
                    translated_title,
                    article["link"]
                )

                print("Опубликовано без изображения")

        except Exception as error:
            print(f"Ошибка изображения: {error}")

            # Если фото не удалось отправить,
            # всё равно публикуем новость текстом
            send_text(
                translated_title,
                article["link"]
            )

        posted.add(article["link"])

        print(
            f"Опубликовано: {translated_title}"
        )

    save_posted(posted)

    print(
        f"Всего опубликовано: {len(new_posts)}"
    )


if __name__ == "__main__":
    main()
