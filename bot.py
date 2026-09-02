```python
import os
import json
import html
import re
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

POSTED_FILE = "posted.json"

# Максимум новостей за один запуск
MAX_POSTS_PER_RUN = 2

# Минимальная важность новости
MIN_SCORE = 7

# Сколько новостей анализируем перед выбором лучших
MAX_CANDIDATES = 40


# ============================================================
# ИСТОЧНИКИ НОВОСТЕЙ
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
# ЗАГРУЗКА / СОХРАНЕНИЕ ОПУБЛИКОВАННЫХ НОВОСТЕЙ
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

    except Exception:
        pass

    return set()


def save_posted(posted):

    with open(
        POSTED_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            list(posted)[-1500:],
            f,
            ensure_ascii=False,
            indent=2
        )


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

    try:

        url = (
            "https://api.mymemory.translated.net/get"
        )

        response = requests.get(
            url,
            params={
                "q": text,
                "langpair": "en|ru"
            },
            timeout=10
        )

        data = response.json()

        translated = (
            data
            .get("responseData", {})
            .get("translatedText", "")
        )

        if translated:
            return translated

    except Exception as e:

        print(
            "Translation error:",
            e
        )

    return text


# ============================================================
# ОПРЕДЕЛЕНИЕ СТРАНЫ / КАТЕГОРИИ
# ============================================================

def detect_category(
    title,
    description
):

    text = (
        f"{title} {description}"
        .lower()
    )

    # США

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


    # Россия

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


    # Технологии

    technology_words = [
        "artificial intelligence",
        "technology",
        "technology company",
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


    # Рынки

    market_words = [
        "stock",
        "stocks",
        "shares",
        "market",
        "markets",
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


    # Экономика

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


    # Бизнес

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
# ОЦЕНКА ВАЖНОСТИ
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


    # --------------------------------------------------------
    # КРУПНЫЕ КОМПАНИИ
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # ОЧЕНЬ ВАЖНЫЕ СОБЫТИЯ
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # ФИНАНСЫ
    # --------------------------------------------------------

    finance_words = [

        "stocks",
        "shares",
        "stock market",
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
        "fed",
        "federal reserve",
        "ecb"
    ]

    for word in finance_words:

        if word in text:

            score += 1


    # --------------------------------------------------------
    # БОЛЬШИЕ ДЕНЬГИ
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # ТЕХНОЛОГИИ
    # --------------------------------------------------------

    technology_words = [

        "artificial intelligence",
        "ai",
        "technology",
        "chip",
        "chips",
        "semiconductor"
    ]

    for word in technology_words:

        if word in text:

            score += 1


    # --------------------------------------------------------
    # США
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # РОССИЯ
    # --------------------------------------------------------

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
# GOOGLE NEWS RSS
# ============================================================

def get_google_news_rss(query):

    url = (
        "https://news.google.com/rss/search"
    )

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


# ============================================================
# ПОИСК КАРТИНКИ
# ============================================================

def get_image_from_article(
    article_url
):

    """
    Пытаемся достать главное изображение
    непосредственно со страницы новости.

    Сначала ищем:
    og:image
    twitter:image
    затем обычные изображения.
    """

    if not article_url:
        return None

    try:

        response = requests.get(

            article_url,

            timeout=15,

            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
            }
        )

        if response.status_code != 200:
            return None

        page = response.text


        # ----------------------------------------------------
        # OG IMAGE
        # ----------------------------------------------------

        patterns = [

            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

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

                image_url = (
                    html.unescape(
                        match.group(1)
                    )
                )

                if image_url.startswith("//"):

                    image_url = (
                        "https:"
                        + image_url
                    )

                elif image_url.startswith("/"):

                    from urllib.parse import urljoin

                    image_url = urljoin(
                        article_url,
                        image_url
                    )

                if image_url.startswith(
                    "http"
                ):

                    return image_url


    except Exception as e:

        print(
            "Image search error:",
            e
        )


    return None


# ============================================================
# ЗАПАСНОЙ ПОИСК ИЗОБРАЖЕНИЯ
# ============================================================

def get_backup_image(
    title
):

    """
    Если страница источника не дала картинку,
    пробуем получить изображение через
    Google News thumbnail URL.
    """

    try:

        query = quote(
            title[:150]
        )

        # Google News иногда отдаёт изображения
        # через результат поиска.
        url = (
            "https://news.google.com/rss/search"
            f"?q={query}"
            "&hl=en-US"
            "&gl=US"
            "&ceid=US:en"
        )

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            }
        )

        if response.status_code != 200:
            return None

        root = ET.fromstring(
            response.text
        )

        item = root.find(
            ".//item"
        )

        if item is None:
            return None

        # Иногда media:content находится
        # в namespace.
        for child in item:

            tag = child.tag.lower()

            if (
                "media:content" in tag
                or "content" in tag
            ):

                url_value = child.attrib.get(
                    "url"
                )

                if (
                    url_value
                    and
                    url_value.startswith("http")
                ):

                    return url_value

    except Exception as e:

        print(
            "Backup image error:",
            e
        )

    return None


# ============================================================
# RSS PARSER
# ============================================================

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


            category = detect_category(

                title,

                description
            )


            hashtags = make_hashtags(
                category
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
                    hashtags,

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
# ПРОФЕССИОНАЛЬНЫЙ АНАЛИЗ
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


    # --------------------------------------------------------
    # КЛЮЧЕВЫЕ ТИПЫ СОБЫТИЙ
    # --------------------------------------------------------

    if any(
        word in text
        for word in [
            "acquisition",
            "acquires",
            "merger"
        ]
    ):

        return (
            "Сделка может существенно "
            "изменить позиции компаний "
            "на рынке и повлиять на "
            "конкурентную среду."
        )


    if any(
        word in text
        for word in [
            "ipo",
            "shares",
            "stock",
            "stocks"
        ]
    ):

        return (
            "Новость важна для инвесторов: "
            "изменение ожиданий рынка может "
            "повлиять на стоимость активов "
            "и инвестиционные стратегии."
        )


    if any(
        word in text
        for word in [
            "inflation",
            "interest rate",
            "central bank",
            "federal reserve",
            "fed"
        ]
    ):

        return (
            "Решение способно повлиять "
            "на стоимость кредитов, "
            "инвестиционную активность "
            "и динамику финансовых рынков."
        )


    if any(
        word in text
        for word in [
            "artificial intelligence",
            "ai",
            "semiconductor",
            "chips"
        ]
    ):

        return (
            "Событие может повлиять "
            "на инвестиции в технологии, "
            "конкуренцию между компаниями "
            "и дальнейшее развитие отрасли."
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
            "может отразиться на издержках "
            "компаний, цепочках поставок "
            "и международной торговле."
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
            "Событие несёт повышенные "
            "риски для компании и может "
            "иметь последствия для "
            "кредиторов, инвесторов "
            "и отрасли."
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
            "Финансовые результаты позволяют "
            "оценить состояние бизнеса "
            "и ожидания инвесторов "
            "относительно дальнейшего роста."
        )


    # --------------------------------------------------------
    # ОБЩИЙ АНАЛИЗ
    # --------------------------------------------------------

    if score >= 9:

        return (
            "Событие имеет высокую "
            "значимость для бизнеса "
            "и может заметно повлиять "
            "на рынок или ожидания инвесторов."
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
# ФОРМАТИРОВАНИЕ ПОСТА
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


    # Ограничиваем описание

    if len(description_ru) > 600:

        description_ru = (

            description_ru[:600]

            .rsplit(
                " ",
                1
            )[0]

            + "..."
        )


    category = html.escape(
        item["category"]
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


    post = (

        f"<b>{category}</b>\n\n"

        f"<b>{title_ru}</b>\n"
    )


    if description_ru:

        post += (
            f"\n{description_ru}\n"
        )


    post += (
        f"\n<b>📊 Почему это важно:</b>\n"
        f"{analysis}\n"
    )


    if item["date"]:

        post += (
            f"\n🕒 {item['date']}\n"
        )


    post += (

        f"\n🔥 Важность: "
        f"<b>{item['score']}/10</b>\n"

        f"\n{item['hashtags']}"
    )


    return post


# ============================================================
# КНОПКА
# ============================================================

def get_keyboard(link):

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
# ОТПРАВКА ФОТО
# ============================================================

def send_photo(
    photo_url,
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


    payload = {

        "chat_id":
            CHANNEL,

        "photo":
            photo_url,

        "caption":
            caption,

        "parse_mode":
            "HTML",

        "reply_markup":
            json.dumps(
                keyboard
            )
    }


    try:

        response = requests.post(

            url,

            data=payload,

            timeout=30
        )


        print(
            "Telegram photo:",
            response.status_code
        )


        if response.ok:

            return True


        print(
            response.text
        )


    except Exception as e:

        print(
            "Photo sending error:",
            e
        )


    return False


# ============================================================
# ОТПРАВКА ТЕКСТА, ЕСЛИ ФОТО НЕ НАШЛОСЬ
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
                keyboard
            )
    }


    try:

        response = requests.post(

            url,

            json=payload,

            timeout=20
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
            "Telegram error:",
            e
        )


    return False


# ============================================================
# ПОЛУЧЕНИЕ КАРТИНКИ
# ============================================================

def find_image(item):

    print(
        "Ищем изображение:"
        f" {item['title']}"
    )


    # Сначала пытаемся взять
    # главное изображение статьи

    image = get_image_from_article(

        item["link"]
    )


    if image:

        print(
            "Найдена картинка статьи"
        )

        return image


    # Затем запасной вариант

    image = get_backup_image(

        item["title"]
    )


    if image:

        print(
            "Найдена запасная картинка"
        )

        return image


    print(
        "Картинка не найдена"
    )

    return None


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
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
        "================================"
    )

    print(
        "      BUSINESS NEWS BOT"
    )

    print(
        "================================"
    )

    print(
        "Получаем новости..."
    )


    # --------------------------------------------------------
    # СОБИРАЕМ НОВОСТИ
    # --------------------------------------------------------

    for feed in FEEDS:

        print(
            f"\nИсточник: {feed['name']}"
        )


        xml_text = (
            get_google_news_rss(
                feed["query"]
            )
        )


        news = parse_rss(

            xml_text,

            feed["name"],

            feed["bonus"]
        )


        all_news.extend(
            news
        )


    print(
        f"\nВсего найдено: "
        f"{len(all_news)}"
    )


    # --------------------------------------------------------
    # УДАЛЯЕМ ДУБЛИКАТЫ
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
    # СОРТИРОВКА
    # --------------------------------------------------------

    unique_news.sort(

        key=lambda x:
            x["score"],

        reverse=True
    )


    unique_news = (
        unique_news[
            :MAX_CANDIDATES
        ]
    )


    print(
        f"Кандидатов после "
        f"фильтрации: "
        f"{len(unique_news)}"
    )


    # --------------------------------------------------------
    # ПУБЛИКАЦИЯ
    # --------------------------------------------------------

    published = 0


    for item in unique_news:

        if item["score"] < MIN_SCORE:

            print(
                "Пропуск слабой новости:",
                item["score"],
                item["title"]
            )

            continue


        if published >= MAX_POSTS_PER_RUN:

            break


        # Получаем изображение

        item["image"] = find_image(
            item
        )


        # Создаём пост

        text = format_post(
            item
        )


        print(
            "\n--------------------------------"
        )

        print(
            "Публикуем:"
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

        print(
            "Фото:",
            bool(item["image"])
        )


        success = False


        # ----------------------------------------------------
        # ЕСЛИ ЕСТЬ ФОТО
        # ----------------------------------------------------

        if item["image"]:

            success = send_photo(

                item["image"],

                text,

                item["link"]
            )


        # ----------------------------------------------------
        # ЕСЛИ ФОТО НЕ ОТПРАВИЛОСЬ
        # ----------------------------------------------------

        if not success:

            print(
                "Фото не отправилось. "
                "Отправляем текст."
            )


            success = send_message(

                text,

                item["link"]
            )


        # ----------------------------------------------------
        # СОХРАНЯЕМ
        # ----------------------------------------------------

        if success:

            posted.add(
                item["link"]
            )

            published += 1


    save_posted(
        posted
    )


    print(
        "\n================================"
    )

    print(
        f"Готово. Опубликовано: "
        f"{published}"
    )

    print(
        "================================"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
```
