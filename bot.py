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


# --------------------------------------------------
# Работа с уже опубликованными новостями
# --------------------------------------------------

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


# --------------------------------------------------
# Получение новостей
# --------------------------------------------------

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
            "source": source or "Источник",
            "image": image
        })

    return news


# --------------------------------------------------
# Перевод
# --------------------------------------------------

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

        print(
            f"Ошибка перевода: {error}"
        )

    return text


# --------------------------------------------------
# Очистка описания
# --------------------------------------------------

def clean_description(text):

    if not text:
        return ""

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


def shorten_text(text, max_length=500):

    if not text:
        return ""

    if len(text) <= max_length:
        return text

    shortened = text[:max_length]

    last_space = shortened.rfind(" ")

    if last_space > 100:
        shortened = shortened[:last_space]

    return shortened + "…"


# --------------------------------------------------
# Определение категории
# --------------------------------------------------

def detect_category(title):

    text = title.lower()

    if any(word in text for word in [
        "apple",
        "google",
        "microsoft",
        "amazon",
        "meta",
        "tesla",
        "nvidia",
        "openai",
        "technology",
        "software",
        "artificial intelligence",
        " ai "
    ]):
        return "💻 Технологии"

    if any(word in text for word in [
        "stock",
        "stocks",
        "shares",
        "investor",
        "investment",
        "market",
        "markets",
        "nasdaq",
        "dow",
        "s&p",
        "wall street",
        "ipo"
    ]):
        return "📈 Инвестиции"

    if any(word in text for word in [
        "bank",
        "banks",
        "interest rate",
        "inflation",
        "economy",
        "economic",
        "fed",
        "central bank",
        "ecb",
        "rate cut",
        "rate hike"
    ]):
        return "💰 Экономика"

    if any(word in text for word in [
        "oil",
        "gas",
        "energy",
        "petrol",
        "renewable",
        "electricity"
    ]):
        return "⚡ Энергетика"

    if any(word in text for word in [
        "startup",
        "startups",
        "venture",
        "funding",
        "founder"
    ]):
        return "🚀 Стартапы"

    return "🏢 Бизнес"


# --------------------------------------------------
# Оценка важности
# --------------------------------------------------

def calculate_score(title, description):

    text = (
        title + " " + description
    ).lower()

    score = 0

    # Очень важные события
    critical_words = [
        "breaking",
        "crisis",
        "collapse",
        "emergency",
        "war",
        "sanctions",
        "default",
        "bankruptcy",
        "acquisition",
        "merger",
        "takeover"
    ]

    for word in critical_words:
        if word in text:
            score += 5

    # Крупные компании
    major_companies = [
        "apple",
        "microsoft",
        "google",
        "alphabet",
        "amazon",
        "meta",
        "tesla",
        "nvidia",
        "openai",
        "berkshire"
    ]

    for word in major_companies:
        if word in text:
            score += 3

    # Финансы
    finance_words = [
        "interest rate",
        "inflation",
        "federal reserve",
        "fed",
        "ecb",
        "central bank",
        "stock market",
        "stocks",
        "shares",
        "ipo",
        "investment"
    ]

    for word in finance_words:
        if word in text:
            score += 3

    # Большие сделки
    deal_words = [
        "billion",
        "million",
        "deal",
        "acquisition",
        "merger",
        "investment",
        "funding"
    ]

    for word in deal_words:
        if word in text:
            score += 2

    # Технологии
    technology_words = [
        "artificial intelligence",
        "ai",
        "chip",
        "semiconductor",
        "technology"
    ]

    for word in technology_words:
        if word in text:
            score += 2

    return score


# --------------------------------------------------
# Хэштеги
# --------------------------------------------------

def make_hashtags(category):

    hashtags = {

        "💻 Технологии":
            "#Технологии #IT",

        "📈 Инвестиции":
            "#Инвестиции #Рынки",

        "💰 Экономика":
            "#Экономика #Финансы",

        "⚡ Энергетика":
            "#Энергетика #Бизнес",

        "🚀 Стартапы":
            "#Стартапы #Инвестиции",

        "🏢 Бизнес":
            "#Бизнес #Новости"
    }

    return hashtags.get(
        category,
        "#Бизнес #Новости"
    )


# --------------------------------------------------
# Формирование публикации
# --------------------------------------------------

def build_caption(
    title,
    description,
    source,
    score
):

    category = detect_category(title)

    hashtags = make_hashtags(category)

    clean_text = clean_description(
        description
    )

    translated_description = translate_text(
        clean_text
    )

    translated_description = shorten_text(
        translated_description
    )

    safe_title = html.escape(title)

    safe_description = html.escape(
        translated_description
    )

    safe_source = html.escape(
        source
    )

    # Определяем важность
    if score >= 10:

        importance = (
            "🚨 <b>ВАЖНО</b>\n\n"
        )

    elif score >= 6:

        importance = (
            "🔥 <b>ГЛАВНОЕ СОБЫТИЕ</b>\n\n"
        )

    else:

        importance = ""

    text = (
        "🏢 <b>МРК | БИЗНЕС НОВОСТИ</b>\n\n"
        f"{importance}"
        f"📰 <b>{safe_title}</b>\n\n"
        f"{category}\n\n"
    )

    if safe_description:

        text += (
            "📌 <b>Коротко:</b>\n"
            f"{safe_description}\n\n"
        )

    text += (
        f"🗞 <b>Источник:</b> "
        f"{safe_source}\n\n"
        f"{hashtags}"
    )

    return text


# --------------------------------------------------
# Отправка текста
# --------------------------------------------------

def send_text(
    title,
    description,
    source,
    link,
    score
):

    caption = build_caption(
        title,
        description,
        source,
        score
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

    url = (
        f"https://api.telegram.org/"
        f"bot{TOKEN}/sendMessage"
    )

    response = requests.post(

        url,

        data={

            "chat_id": CHANNEL,

            "text": caption,

            "parse_mode": "HTML",

            "reply_markup":
                json.dumps(keyboard)

        },

        timeout=20
    )

    response.raise_for_status()


# --------------------------------------------------
# Отправка фотографии
# --------------------------------------------------

def send_photo(
    title,
    description,
    source,
    link,
    image,
    score
):

    caption = build_caption(
        title,
        description,
        source,
        score
    )

    keyboard = {

        "inline_keyboard": [

            [
                {
                    "text":
                        "🔗 Читать источник",

                    "url": link
                }
            ]

        ]
    }

    url = (
        f"https://api.telegram.org/"
        f"bot{TOKEN}/sendPhoto"
    )

    response = requests.post(

        url,

        data={

            "chat_id": CHANNEL,

            "photo": image,

            "caption": caption,

            "parse_mode": "HTML",

            "reply_markup":
                json.dumps(keyboard)

        },

        timeout=30
    )

    response.raise_for_status()


# --------------------------------------------------
# Главная функция
# --------------------------------------------------

def main():

    posted = load_posted()

    news = get_news()

    candidates = []

    for article in news:

        if article["link"] in posted:
            continue

        score = calculate_score(
            article["title"],
            article["description"]
        )

        article["score"] = score

        candidates.append(article)

    # Сначала самые важные
    candidates.sort(
        key=lambda article:
            article["score"],
        reverse=True
    )

    # Не более 2 новостей за запуск
    selected = candidates[:2]

    print(
        f"Найдено новых новостей: "
        f"{len(candidates)}"
    )

    print(
        f"Выбрано для публикации: "
        f"{len(selected)}"
    )

    for article in selected:

        print(
            f"Важность: "
            f"{article['score']}"
        )

        print(
            f"Новость: "
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

                    article["image"],

                    article["score"]
                )

                print(
                    "Опубликовано с изображением"
                )

            else:

                send_text(

                    translated_title,

                    article["description"],

                    article["source"],

                    article["link"],

                    article["score"]
                )

                print(
                    "Опубликовано без изображения"
                )

        except Exception as error:

            print(
                f"Ошибка публикации: "
                f"{error}"
            )

            # Если фото не сработало,
            # отправляем текст
            send_text(

                translated_title,

                article["description"],

                article["source"],

                article["link"],

                article["score"]
            )

        posted.add(
            article["link"]
        )

    save_posted(posted)

    print(
        "Работа бота завершена."
    )


if __name__ == "__main__":
    main()
