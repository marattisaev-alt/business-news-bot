import os
import json
import html
import re
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

POSTED_FILE = "posted.json"

MAX_POSTS_PER_RUN = 2
MIN_SCORE = 7

MAX_CANDIDATES = 50

REQUEST_TIMEOUT = 20


# ============================================================
# ИСТОЧНИКИ
# ============================================================

FEEDS = [

    {
        "name": "Reuters",
        "query": "site:reuters.com/business",
        "bonus": 4
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
    },

    {
        "name": "Рынки",
        "query": "stock market OR investing OR IPO OR Wall Street",
        "bonus": 2
    },

    {
        "name": "Экономика",
        "query": "economy OR inflation OR interest rates OR central bank",
        "bonus": 2
    },

    {
        "name": "Технологии",
        "query": "artificial intelligence OR technology OR chips OR semiconductor",
        "bonus": 2
    },

    {
        "name": "Бизнес",
        "query": "business companies corporate earnings revenue",
        "bonus": 1
    }
]


# ============================================================
# ФАЙЛ ОПУБЛИКОВАННЫХ НОВОСТЕЙ
# ============================================================

def load_posted():

    try:

        with open(
            POSTED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, list):

                return set(data)

    except Exception as e:

        print("Posted file error:", e)

    return set()


def save_posted(posted):

    try:

        with open(
            POSTED_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                list(posted)[-2000:],
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print("Save error:", e)


# ============================================================
# ОЧИСТКА ТЕКСТА
# ============================================================

def clean_html(text):

    if not text:
        return ""

    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# ПЕРЕВОД
# ============================================================

def translate_to_russian(text):

    if not text:
        return ""

    # Если текст уже похож на русский,
    # не тратим запрос на перевод.

    cyrillic = len(
        re.findall(
            r"[А-Яа-яЁё]",
            text
        )
    )

    latin = len(
        re.findall(
            r"[A-Za-z]",
            text
        )
    )

    if cyrillic > latin:

        return text

    try:

        response = requests.get(

            "https://api.mymemory.translated.net/get",

            params={
                "q": text[:4500],
                "langpair": "en|ru"
            },

            timeout=10
        )

        data = response.json()

        result = (
            data
            .get("responseData", {})
            .get("translatedText", "")
        )

        if result:

            return result

    except Exception as e:

        print(
            "Translation error:",
            e
        )

    return text


# ============================================================
# КАТЕГОРИЯ
# ============================================================

def detect_category(
    title,
    description
):

    text = (
        f"{title} {description}"
        .lower()
    )


    usa_words = [

        "united states",
        "u.s.",
        "american",
        "washington",
        "wall street",
        "new york",
        "california",
        "silicon valley"
    ]

    if any(
        word in text
        for word in usa_words
    ):

        return "🇺🇸 США"


    russia_words = [

        "russia",
        "russian",
        "moscow",
        "ruble",
        "rubles",
        "рубль",
        "рублей"
    ]

    if any(
        word in text
        for word in russia_words
    ):

        return "🇷🇺 Россия"


    technology_words = [

        "artificial intelligence",
        "technology",
        "chip",
        "chips",
        "semiconductor",
        "software",
        "robot",
        "robotics",
        "ai "
    ]

    if any(
        word in text
        for word in technology_words
    ):

        return "🤖 Технологии"


    market_words = [

        "stock market",
        "stocks",
        "shares",
        "investor",
        "investors",
        "ipo",
        "investment",
        "wall street"
    ]

    if any(
        word in text
        for word in market_words
    ):

        return "📈 Рынки"


    economy_words = [

        "inflation",
        "interest rate",
        "interest rates",
        "central bank",
        "economy",
        "economic",
        "gdp",
        "recession"
    ]

    if any(
        word in text
        for word in economy_words
    ):

        return "💰 Экономика"


    business_words = [

        "business",
        "company",
        "companies",
        "corporation",
        "revenue",
        "profit",
        "earnings",
        "ceo"
    ]

    if any(
        word in text
        for word in business_words
    ):

        return "🏢 Бизнес"


    return "📰 Новости"


# ============================================================
# ХЭШТЕГИ
# ============================================================

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

    return hashtags.get(
        category,
        "#Новости"
    )


# ============================================================
# РЕЙТИНГ НОВОСТИ
# ============================================================

def calculate_score(
    title,
    description,
    bonus
):

    text = (
        f"{title} {description}"
        .lower()
    )

    score = 2


    # Крупные компании

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
        "netflix",
        "uber",
        "boeing",
        "walmart",
        "visa",
        "mastercard",
        "jpmorgan",
        "goldman sachs",
        "morgan stanley",
        "blackrock",
        "berkshire hathaway"
    ]

    for word in major_companies:

        if word in text:

            score += 2


    # Очень важные события

    critical_words = [

        "breaking",
        "urgent",
        "crisis",
        "bankruptcy",
        "default",
        "collapse",
        "acquisition",
        "acquires",
        "merger",
        "deal",
        "agreement",
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

    for word in critical_words:

        if word in text:

            score += 2


    # Финансовые события

    finance_words = [

        "stock",
        "stocks",
        "shares",
        "market",
        "markets",
        "investor",
        "investors",
        "investment",
        "ipo",
        "profit",
        "profits",
        "revenue",
        "earnings",
        "inflation",
        "interest rate",
        "interest rates",
        "central bank",
        "federal reserve",
        "fed",
        "ecb"
    ]

    for word in finance_words:

        if word in text:

            score += 1


    # Деньги

    money_words = [

        "million",
        "billion",
        "trillion",
        "dollar",
        "dollars",
        "euro",
        "euros",
        "ruble",
        "rubles"
    ]

    for word in money_words:

        if word in text:

            score += 1


    # Технологии

    technology_words = [

        "artificial intelligence",
        "technology",
        "chip",
        "chips",
        "semiconductor",
        "robotics"
    ]

    for word in technology_words:

        if word in text:

            score += 1


    # Региональные события

    usa_words = [

        "united states",
        "u.s.",
        "american",
        "washington",
        "wall street"
    ]

    for word in usa_words:

        if word in text:

            score += 1


    russia_words = [

        "russia",
        "russian",
        "moscow",
        "ruble",
        "rubles"
    ]

    for word in russia_words:

        if word in text:

            score += 1


    score += bonus

    return min(
        score,
        10
    )


# ============================================================
# АНТИ-КЛИКБЕЙТ
# ============================================================

def clickbait_penalty(title):

    text = title.lower()

    bad_words = [

        "you won't believe",
        "shocking",
        "secret",
        "revealed",
        "what happens next",
        "this is why",
        "you need to know",
        "unbelievable"
    ]

    penalty = 0

    for word in bad_words:

        if word in text:

            penalty += 1


    if title.count("!") >= 2:

        penalty += 1


    return penalty


# ============================================================
# ПОХОЖЕСТЬ НОВОСТЕЙ
# ============================================================

def normalize_words(text):

    text = text.lower()

    text = re.sub(
        r"[^a-zа-яё0-9 ]",
        " ",
        text
    )

    words = set(
        word
        for word in text.split()
        if len(word) > 3
    )

    return words


def are_similar_titles(
    title1,
    title2
):

    words1 = normalize_words(
        title1
    )

    words2 = normalize_words(
        title2
    )

    if not words1 or not words2:

        return False

    intersection = (
        words1 & words2
    )

    union = (
        words1 | words2
    )

    similarity = (
        len(intersection)
        /
        len(union)
    )

    return similarity >= 0.55


def remove_similar_news(news):

    result = []

    for item in news:

        duplicate = False

        for existing in result:

            if are_similar_titles(
                item["title"],
                existing["title"]
            ):

                duplicate = True

                # Если новая версия важнее,
                # заменяем старую.

                if (
                    item["score"]
                    >
                    existing["score"]
                ):

                    result.remove(
                        existing
                    )

                    duplicate = False

                break


        if not duplicate:

            result.append(
                item
            )


    return result


# ============================================================
# ДАТА
# ============================================================

def parse_date(date_string):

    if not date_string:

        return ""

    try:

        dt = parsedate_to_datetime(
            date_string
        )

        return dt.strftime(
            "%d.%m.%Y %H:%M"
        )

    except Exception:

        return ""


# ============================================================
# RSS
# ============================================================

def get_google_news_rss(
    query
):

    try:

        response = requests.get(

            "https://news.google.com/rss/search",

            params={

                "q": query,

                "hl": "en-US",

                "gl": "US",

                "ceid": "US:en"
            },

            timeout=REQUEST_TIMEOUT,

            headers={

                "User-Agent":
                    "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        return response.text

    except Exception as e:

        print(
            "RSS error:",
            e
        )

        return ""


def parse_rss(
    xml_text,
    source_name,
    bonus
):

    if not xml_text:

        return []

    items = []

    try:

        root = ET.fromstring(
            xml_text
        )

        for item in root.findall(
            ".//item"
        ):

            title_element = (
                item.find("title")
            )

            link_element = (
                item.find("link")
            )

            description_element = (
                item.find("description")
            )

            date_element = (
                item.find("pubDate")
            )


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


            title = clean_html(
                title
            )

            description = clean_html(
                description
            )


            if not title or not link:

                continue


            score = calculate_score(

                title,

                description,

                bonus
            )


            score -= clickbait_penalty(
                title
            )


            score = max(
                1,
                min(score, 10)
            )


            category = detect_category(

                title,

                description
            )


            items.append({

                "title":
                    title,

                "description":
                    description,

                "link":
                    link,

                "source":
                    source_name,

                "date":
                    parse_date(
                        pub_date
                    ),

                "score":
                    score,

                "category":
                    category,

                "hashtags":
                    make_hashtags(
                        category
                    ),

                "image":
                    None
            })


    except Exception as e:

        print(
            "RSS parsing error:",
            e
        )


    return items


# ============================================================
# ПОИСК OG:IMAGE
# ============================================================

def extract_meta_image(
    page,
    article_url
):

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            page,
            re.IGNORECASE
        )

        if match:

            image_url = html.unescape(
                match.group(1)
            )

            image_url = image_url.strip()


            if image_url.startswith(
                "//"
            ):

                image_url = (
                    "https:"
                    + image_url
                )


            elif image_url.startswith(
                "/"
            ):

                image_url = urljoin(
                    article_url,
                    image_url
                )


            if image_url.startswith(
                "http"
            ):

                return image_url


    return None


# ============================================================
# ПОИСК ФОТО НА СТРАНИЦЕ
# ============================================================

def get_image_from_article(
    article_url
):

    if not article_url:

        return None


    try:

        response = requests.get(

            article_url,

            timeout=REQUEST_TIMEOUT,

            allow_redirects=True,

            headers={

                "User-Agent":
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
            }
        )


        if response.status_code != 200:

            print(
                "Article status:",
                response.status_code
            )

            return None


        image_url = extract_meta_image(

            response.text,

            response.url
        )


        if image_url:

            print(
                "Найдена OG-картинка:"
            )

            print(
                image_url[:200]
            )

            return image_url


    except Exception as e:

        print(
            "Article image error:",
            e
        )


    return None


# ============================================================
# СКАЧИВАНИЕ ФОТО
# ============================================================

def download_image(
    image_url
):

    if not image_url:

        return None


    try:

        response = requests.get(

            image_url,

            timeout=REQUEST_TIMEOUT,

            stream=True,

            headers={

                "User-Agent":
                    "Mozilla/5.0"
            }
        )


        if response.status_code != 200:

            print(
                "Image status:",
                response.status_code
            )

            return None


        content_type = (
            response.headers
            .get(
                "Content-Type",
                ""
            )
            .lower()
        )


        if (
            "image"
            not in content_type
        ):

            print(
                "Это не изображение:",
                content_type
            )

            return None


        content_length = response.headers.get(
            "Content-Length"
        )


        if content_length:

            try:

                if int(
                    content_length
                ) > 9_000_000:

                    print(
                        "Изображение слишком большое"
                    )

                    return None

            except Exception:

                pass


        extension = ".jpg"


        if "png" in content_type:

            extension = ".png"

        elif "webp" in content_type:

            extension = ".webp"

        elif "gif" in content_type:

            extension = ".gif"


        filename = (
            "news_image"
            + extension
        )


        with open(
            filename,
            "wb"
        ) as f:

            total = 0

            for chunk in response.iter_content(
                chunk_size=8192
            ):

                if not chunk:

                    continue


                total += len(chunk)


                # Безопасный предел

                if total > 9_000_000:

                    print(
                        "Файл превысил лимит"
                    )

                    f.close()

                    try:
                        os.remove(
                            filename
                        )
                    except Exception:
                        pass

                    return None


                f.write(chunk)


        if os.path.getsize(
            filename
        ) < 1000:

            try:

                os.remove(
                    filename
                )

            except Exception:

                pass

            return None


        print(
            "Фото скачано:",
            filename,
            os.path.getsize(
                filename
            ),
            "bytes"
        )


        return filename


    except Exception as e:

        print(
            "Download image error:",
            e
        )

        return None


# ============================================================
# АНАЛИЗ НОВОСТИ
# ============================================================

def generate_analysis(
    title,
    description,
    category,
    score
):

    text = (
        f"{title} {description}"
        .lower()
    )


    if any(
        word in text
        for word in [
            "acquisition",
            "acquires",
            "merger"
        ]
    ):

        return (
            "Сделка может изменить "
            "конкурентную позицию компаний "
            "и повлиять на структуру рынка."
        )


    if any(
        word in text
        for word in [
            "ipo",
            "stock",
            "stocks",
            "shares"
        ]
    ):

        return (
            "Новость важна для инвесторов: "
            "она способна изменить ожидания "
            "рынка и стоимость активов."
        )


    if any(
        word in text
        for word in [
            "inflation",
            "interest rate",
            "interest rates",
            "central bank",
            "federal reserve",
            "fed"
        ]
    ):

        return (
            "Решение может повлиять "
            "на стоимость кредитов, "
            "инвестиционную активность "
            "и финансовые рынки."
        )


    if any(
        word in text
        for word in [
            "artificial intelligence",
            "ai",
            "semiconductor",
            "chip",
            "chips"
        ]
    ):

        return (
            "Событие может усилить конкуренцию "
            "в технологическом секторе "
            "и повлиять на инвестиции "
            "в инфраструктуру ИИ."
        )


    if any(
        word in text
        for word in [
            "tariff",
            "tariffs",
            "sanctions"
        ]
    ):

        return (
            "Изменение торговых условий "
            "может увеличить издержки бизнеса, "
            "повлиять на цепочки поставок "
            "и международную торговлю."
        )


    if any(
        word in text
        for word in [
            "bankruptcy",
            "default",
            "collapse"
        ]
    ):

        return (
            "Событие повышает риски "
            "для компании, кредиторов "
            "и инвесторов и может иметь "
            "последствия для всей отрасли."
        )


    if any(
        word in text
        for word in [
            "profit",
            "profits",
            "revenue",
            "earnings"
        ]
    ):

        return (
            "Финансовые результаты показывают "
            "состояние бизнеса и могут изменить "
            "ожидания инвесторов относительно "
            "дальнейшего роста компании."
        )


    if score >= 9:

        return (
            "Событие имеет высокую значимость "
            "для бизнеса и способно заметно "
            "повлиять на рынок или ожидания "
            "инвесторов."
        )


    if score >= 8:

        return (
            "Новость заслуживает внимания, "
            "поскольку может повлиять "
            "на компании, рынок "
            "или деловую активность."
        )


    return (
        "Событие представляет интерес "
        "для участников рынка и бизнеса."
    )


# ============================================================
# ФОРМАТ ПОСТА
# ============================================================

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


    # Не даём описанию занимать
    # слишком много места.

    if len(description_ru) > 550:

        description_ru = (

            description_ru[:550]

            .rsplit(
                " ",
                1
            )[0]

            + "..."
        )


    analysis = generate_analysis(

        item["title"],

        item["description"],

        item["category"],

        item["score"]
    )


    analysis = html.escape(
        analysis
    )


    category = html.escape(
        item["category"]
    )


    post = (

        f"<b>{category}</b>\n\n"

        f"<b>{title_ru}</b>"
    )


    if description_ru:

        post += (
            f"\n\n{description_ru}"
        )


    post += (

        f"\n\n"
        f"<b>📊 Почему это важно:</b>\n"
        f"{analysis}"
    )


    if item["date"]:

        post += (
            f"\n\n🕒 {item['date']}"
        )


    post += (

        f"\n\n"
        f"🔥 Важность: "
        f"<b>{item['score']}/10</b>"
        f"\n\n"
        f"{item['hashtags']}"
    )


    # Telegram ограничивает caption
    # для фотографии.
    # Оставляем запас.

    if len(post) > 1000:

        post = post[:995]

        post = (
            post.rsplit(
                " ",
                1
            )[0]
            + "..."
        )


    return post


# ============================================================
# КНОПКА
# ============================================================

def get_keyboard(
    link
):

    return {

        "inline_keyboard": [

            [

                {

                    "text":
                        "🔗 Читать источник",

                    "url":
                        link
                }

            ]

        ]
    }


# ============================================================
# ОТПРАВКА ФОТО В TELEGRAM
# ============================================================

def send_photo_file(
    filename,
    caption,
    link
):

    url = (

        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendPhoto"
    )


    keyboard = get_keyboard(
        link
    )


    try:

        with open(
            filename,
            "rb"
        ) as photo:

            response = requests.post(

                url,

                data={

                    "chat_id":
                        CHANNEL,

                    "caption":
                        caption,

                    "parse_mode":
                        "HTML",

                    "reply_markup":
                        json.dumps(
                            keyboard,
                            ensure_ascii=False
                        )
                },

                files={

                    "photo":
                        photo
                },

                timeout=40
            )


        print(
            "Telegram photo:",
            response.status_code
        )


        if response.ok:

            return True


        print(
            "Telegram photo error:",
            response.text
        )


    except Exception as e:

        print(
            "Send photo error:",
            e
        )


    return False


# ============================================================
# ОТПРАВКА ТЕКСТА
# ============================================================

def send_message(
    text,
    link
):

    url = (

        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )


    keyboard = get_keyboard(
        link
    )


    payload = {

        "chat_id":
            CHANNEL,

        "text":
            text,

        "parse_mode":
            "HTML",

        "disable_web_page_preview":
            False,

        "reply_markup":
            json.dumps(
                keyboard,
                ensure_ascii=False
            )
    }


    try:

        response = requests.post(

            url,

            json=payload,

            timeout=30
        )


        print(
            "Telegram:",
            response.status_code
        )


        if response.ok:

            return True


        print(
            response.text
        )


    except Exception as e:

        print(
            "Send text error:",
            e
        )


    return False


# ============================================================
# ПОИСК ФОТО ДЛЯ НОВОСТИ
# ============================================================

def find_image(item):

    print(
        "\n🖼 Ищем фото:"
    )

    print(
        item["title"]
    )


    image_url = get_image_from_article(

        item["link"]
    )


    if not image_url:

        print(
            "Фото на странице не найдено."
        )

        return None


    filename = download_image(
        image_url
    )


    if filename:

        return filename


    return None


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN is missing"
        )

        return


    if not CHANNEL:

        print(
            "ERROR: CHANNEL is missing"
        )

        return


    posted = load_posted()


    all_news = []


    print(
        "======================================"
    )

    print(
        "       МРК BUSINESS NEWS BOT 3.0"
    )

    print(
        "======================================"
    )


    # --------------------------------------------------------
    # СОБИРАЕМ НОВОСТИ
    # --------------------------------------------------------

    for feed in FEEDS:

        print(
            f"\n🔎 {feed['name']}"
        )


        xml_text = get_google_news_rss(

            feed["query"]
        )


        news = parse_rss(

            xml_text,

            feed["name"],

            feed["bonus"]
        )


        print(
            "Найдено:",
            len(news)
        )


        all_news.extend(
            news
        )


    print(
        "\nВсего кандидатов:",
        len(all_news)
    )


    # --------------------------------------------------------
    # УБИРАЕМ ПОВТОРЫ ПО ССЫЛКАМ
    # --------------------------------------------------------

    unique_news = []

    seen_links = set()


    for item in all_news:

        link = item["link"]


        if link in seen_links:

            continue


        seen_links.add(
            link
        )


        if link in posted:

            continue


        unique_news.append(
            item
        )


    # --------------------------------------------------------
    # УБИРАЕМ СХОЖИЕ НОВОСТИ
    # --------------------------------------------------------

    unique_news = remove_similar_news(
        unique_news
    )


    # --------------------------------------------------------
    # СОРТИРОВКА ПО ВАЖНОСТИ
    # --------------------------------------------------------

    unique_news.sort(

        key=lambda x:
            x["score"],

        reverse=True
    )


    unique_news = unique_news[
        :MAX_CANDIDATES
    ]


    print(
        "\nПосле фильтра:",
        len(unique_news)
    )


    # --------------------------------------------------------
    # ПОКАЗЫВАЕМ ТОП
    # --------------------------------------------------------

    print(
        "\nТОП НОВОСТЕЙ:"
    )


    for item in unique_news[:10]:

        print(

            f"{item['score']}/10 | "
            f"{item['category']} | "
            f"{item['title'][:100]}"
        )


    # --------------------------------------------------------
    # ПУБЛИКАЦИЯ
    # --------------------------------------------------------

    published = 0


    for item in unique_news:

        if item["score"] < MIN_SCORE:

            print(
                "\n⛔ Пропуск:",
                item["score"],
                item["title"]
            )

            continue


        if published >= MAX_POSTS_PER_RUN:

            break


        print(
            "\n======================================"
        )

        print(
            "🔥 ВЫБРАНА НОВОСТЬ"
        )

        print(
            item["title"]
        )

        print(
            "Категория:",
            item["category"]
        )

        print(
            "Важность:",
            item["score"],
            "/10"
        )


        # ----------------------------------------------------
        # ИЩЕМ ФОТО
        # ----------------------------------------------------

        image_file = find_image(
            item
        )


        # ----------------------------------------------------
        # СОЗДАЁМ ПОСТ
        # ----------------------------------------------------

        text = format_post(
            item
        )


        success = False


        # ----------------------------------------------------
        # ПУБЛИКАЦИЯ С ФОТО
        # ----------------------------------------------------

        if image_file:

            success = send_photo_file(

                image_file,

                text,

                item["link"]
            )


        # ----------------------------------------------------
        # ЕСЛИ ФОТО НЕ СРАБОТАЛО
        # ----------------------------------------------------

        if not success:

            print(
                "⚠️ Фото не отправилось."
            )

            print(
                "Публикуем текстовую версию."
            )


            success = send_message(

                text,

                item["link"]
            )


        # ----------------------------------------------------
        # УДАЛЯЕМ ВРЕМЕННЫЙ ФАЙЛ
        # ----------------------------------------------------

        if image_file:

            try:

                os.remove(
                    image_file
                )

            except Exception:

                pass


        # ----------------------------------------------------
        # СОХРАНЯЕМ НОВОСТЬ
        # ----------------------------------------------------

        if success:

            posted.add(
                item["link"]
            )

            published += 1

            print(
                "✅ Опубликовано"
            )

        else:

            print(
                "❌ Не удалось опубликовать"
            )


    save_posted(
        posted
    )


    print(
        "\n======================================"
    )

    print(
        f"ГОТОВО. Опубликовано: {published}"
    )

    print(
        "======================================"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
