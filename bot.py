import os
import re
import json
import html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin

import requests


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")

# Сколько новостей публиковать за один запуск
MAX_POSTS_PER_RUN = 2

# Максимальный возраст новости
MAX_NEWS_AGE_HOURS = 48

# Файл уже опубликованных новостей
POSTED_FILE = "posted.json"

# Максимальный размер картинки
MAX_IMAGE_SIZE = 9 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# =========================================================
# RSS ИСТОЧНИКИ
# =========================================================

RSS_FEEDS = [
    (
        "Ведомости — Бизнес",
        "https://www.vedomosti.ru/rss/rubric/business",
    ),
    (
        "Ведомости — Экономика",
        "https://www.vedomosti.ru/rss/rubric/economics",
    ),
    (
        "Ведомости — Технологии",
        "https://www.vedomosti.ru/rss/rubric/technology",
    ),
    (
        "Ведомости — Предпринимательство",
        "https://www.vedomosti.ru/rss/rubric/management/entrepreneurship",
    ),
    (
        "Ведомости — Финансы",
        "https://www.vedomosti.ru/rss/rubric/finance",
    ),
    (
        "ЦБ РФ — Новости",
        "https://www.cbr.ru/rss/RssNews",
    ),
    (
        "ЦБ РФ — Пресс-релизы",
        "https://www.cbr.ru/rss/RssPress",
    ),
    (
        "RB.RU — IT",
        "https://rb.ru/feeds/tag/it/",
    ),
    (
        "RB.RU — AI",
        "https://rb.ru/feeds/tag/ai/",
    ),
    (
        "RB.RU — E-commerce",
        "https://rb.ru/feeds/tag/ecommerce/",
    ),
]


# =========================================================
# ТЕМАТИКА
# =========================================================

TOPIC_WORDS = {
    # Бизнес
    "бизнес",
    "компания",
    "компании",
    "предприниматель",
    "предприниматели",
    "предприятие",
    "предприятия",
    "корпорация",
    "выручка",
    "прибыль",
    "убыток",
    "инвестиции",
    "инвестор",
    "инвесторы",
    "сделка",
    "сделки",
    "слияние",
    "поглощение",
    "стартап",
    "стартапы",
    "мсп",
    "малый бизнес",
    "средний бизнес",
    "ритейл",
    "торговля",
    "производство",
    "промышленность",
    "экспорт",
    "импорт",
    "логистика",
    "рынок",
    "рынки",

    # Экономика
    "экономика",
    "экономический",
    "ввп",
    "инфляция",
    "дефляция",
    "ставка",
    "ключевая ставка",
    "центробанк",
    "центральный банк",
    "банк россии",
    "минфин",
    "бюджет",
    "налоги",
    "налог",
    "ндс",
    "рубль",
    "рубля",
    "рублей",
    "занятость",
    "безработица",
    "зарплата",
    "цены",
    "доходы",
    "расходы",
    "кредит",
    "кредиты",
    "ипотека",
    "денежно-кредитная",
    "денежная политика",

    # Предпринимательство
    "предпринимательство",
    "ип",
    "самозанятые",
    "самозанятый",
    "бизнесмен",
    "бизнесмены",
    "бизнес-проект",
    "франшиза",
    "франшизы",
    "венчур",
    "венчурный капитал",
    "финансирование",
    "грант",
    "гранты",
    "акселератор",
    "инкубатор",

    # Технологии
    "технологии",
    "технология",
    "ит",
    "айти",
    "цифровизация",
    "цифровой",
    "искусственный интеллект",
    "ии",
    "нейросеть",
    "нейросети",
    "машинное обучение",
    "робот",
    "роботы",
    "робототехника",
    "программное обеспечение",
    "по",
    "разработка",
    "разработчик",
    "разработчики",
    "приложение",
    "приложения",
    "сервис",
    "сервисы",
    "облако",
    "облачный",
    "дата-центр",
    "дата-центры",
    "кибербезопасность",
    "телеком",
    "связь",
    "микросхема",
    "микросхемы",
    "процессор",
    "квантовый",
    "квантовые",
    "биотехнологии",
    "беспилотник",
    "беспилотники",
}


# =========================================================
# МУСОРНЫЕ ТЕМЫ
# =========================================================

LOW_VALUE_WORDS = {
    "спорт",
    "футбол",
    "хоккей",
    "матч",
    "кино",
    "музыка",
    "шоу",
    "певец",
    "певица",
    "актер",
    "актриса",
    "гороскоп",
    "рецепт",
    "погода",
    "происшествие",
    "криминал",
}


# =========================================================
# ТЕКСТ
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    return clean_text(text).lower()


def escape_html(text):
    return html.escape(str(text), quote=False)


def is_russian(text):
    """
    Проверяем, что заголовок действительно русский.
    """

    text = clean_text(text)

    if not text:
        return False

    cyrillic = len(re.findall(r"[а-яё]", text.lower()))
    latin = len(re.findall(r"[a-z]", text.lower()))

    if cyrillic == 0:
        return False

    if latin == 0:
        return True

    return cyrillic >= latin


def contains_any(text, words):
    text = normalize(text)

    return any(word in text for word in words)


# =========================================================
# ПРОВЕРКА НОВОСТИ
# =========================================================

def article_is_relevant(article):

    title = article.get("title", "")
    description = article.get("description", "")

    text = normalize(title + " " + description)

    # Заголовок должен быть русским
    if not is_russian(title):
        print(f"  [FILTER] Не русский заголовок: {title}")
        return False

    # Должна быть хотя бы одна бизнес/экономическая/технологическая тема
    if not contains_any(text, TOPIC_WORDS):
        print(f"  [FILTER] Не подходит по тематике: {title}")
        return False

    # Если явно присутствует мусорная тема —
    # пропускаем только если есть несколько сильных бизнес-слов
    if contains_any(text, LOW_VALUE_WORDS):

        topic_hits = sum(
            1 for word in TOPIC_WORDS
            if word in text
        )

        if topic_hits < 2:
            print(f"  [FILTER] Мусорная тема: {title}")
            return False

    return True


# =========================================================
# JSON
# =========================================================

def load_json_file(filename, default):

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def save_json_file(filename, data):

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def load_posted():

    data = load_json_file(
        POSTED_FILE,
        []
    )

    if not isinstance(data, list):
        return []

    return data


def save_posted(data):

    save_json_file(
        POSTED_FILE,
        data[-2000:]
    )


# =========================================================
# ДАТЫ
# =========================================================

def parse_date(value):

    if not value:
        return None

    try:

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:

        # Иногда встречается ISO дата
        try:

            value = value.replace(
                "Z",
                "+00:00"
            )

            dt = datetime.fromisoformat(
                value
            )

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt.astimezone(
                timezone.utc
            )

        except Exception:
            return None


def age_hours(value):

    dt = parse_date(value)

    if not dt:
        # Если источник не дал дату,
        # не отбрасываем автоматически.
        return 0

    now = datetime.now(timezone.utc)

    return max(
        0,
        (now - dt).total_seconds() / 3600
    )


# =========================================================
# HTTP
# =========================================================

def fetch(url, timeout=20):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout
        )

        response.raise_for_status()

        return response

    except Exception as e:

        print(
            f"[HTTP ERROR] {url} -> {e}"
        )

        return None


# =========================================================
# RSS
# =========================================================

def parse_rss(xml_text, source):

    articles = []

    try:

        root = ET.fromstring(
            xml_text
        )

    except Exception as e:

        print(
            f"[RSS PARSE ERROR] {source}: {e}"
        )

        return articles

    items = root.findall(
        ".//item"
    )

    # Поддержка Atom
    if not items:

        items = root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )

    for item in items:

        def get_text(tag):

            value = item.findtext(
                tag,
                ""
            )

            return clean_text(value)

        title = get_text("title")
        description = get_text("description")
        link = get_text("link")
        pub_date = get_text("pubDate")

        # Atom link
        if not link:

            atom_link = item.find(
                "{http://www.w3.org/2005/Atom}link"
            )

            if atom_link is not None:

                link = atom_link.attrib.get(
                    "href",
                    ""
                )

        # DC date
        if not pub_date:

            for child in item:

                if child.tag.lower().endswith(
                    "date"
                ):

                    pub_date = clean_text(
                        child.text or ""
                    )

                    break

        # Atom updated/published
        if not pub_date:

            for tag in [
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            ]:

                value = item.findtext(
                    tag,
                    ""
                )

                if value:

                    pub_date = clean_text(
                        value
                    )

                    break

        if not title or not link:
            continue

        articles.append(
            {
                "title": title,
                "description": description,
                "link": link,
                "published": pub_date,
                "source": source,
            }
        )

    return articles


def fetch_all_feeds():

    all_articles = []

    print("\n========== RSS ==========")

    for source, url in RSS_FEEDS:

        print(
            f"\n[RSS] {source}"
        )

        response = fetch(url)

        if not response:

            print(
                "  -> источник недоступен"
            )

            continue

        print(
            f"  -> HTTP {response.status_code}"
        )

        articles = parse_rss(
            response.text,
            source
        )

        print(
            f"  -> получено: {len(articles)}"
        )

        accepted = 0

        for article in articles:

            age = age_hours(
                article.get("published")
            )

            if age > MAX_NEWS_AGE_HOURS:

                continue

            if not article_is_relevant(
                article
            ):

                continue

            all_articles.append(
                article
            )

            accepted += 1

        print(
            f"  -> подходит: {accepted}"
        )

    print(
        f"\nВсего подходящих новостей: {len(all_articles)}"
    )

    return all_articles


# =========================================================
# ДЕДУПЛИКАЦИЯ
# =========================================================

def normalize_link(link):

    link = clean_text(link)

    try:

        parsed = urlparse(link)

        query_parts = []

        for part in parsed.query.split("&"):

            if not part:
                continue

            key = part.split(
                "=",
                1
            )[0].lower()

            if key.startswith("utm_"):
                continue

            if key in {
                "from",
                "ref",
                "source",
                "yclid",
                "fbclid",
            }:
                continue

            query_parts.append(
                part
            )

        query = "&".join(
            query_parts
        )

        return parsed._replace(
            query=query,
            fragment=""
        ).geturl()

    except Exception:

        return link


def article_key(article):

    link = normalize_link(
        article.get("link", "")
    )

    if link:
        return link

    return normalize(
        article.get("title", "")
    )


def important_words(text):

    words = re.findall(
        r"[а-яёa-z0-9]{4,}",
        normalize(text)
    )

    stop_words = {
        "бизнес",
        "компания",
        "компании",
        "россия",
        "российский",
        "российские",
        "новости",
        "которые",
        "который",
        "которых",
        "также",
        "после",
        "будет",
        "будут",
        "этот",
        "этого",
        "своего",
        "свои",
        "может",
        "могут",
        "стало",
        "стали",
    }

    return {
        word
        for word in words
        if word not in stop_words
    }


def similarity(text1, text2):

    a = important_words(text1)
    b = important_words(text2)

    if not a or not b:
        return 0

    intersection = len(
        a & b
    )

    union = len(
        a | b
    )

    return intersection / union


def remove_duplicates(articles):

    result = []

    seen_links = set()

    articles = sorted(
        articles,
        key=lambda x:
            parse_date(
                x.get("published")
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            ),
        reverse=True
    )

    for article in articles:

        key = article_key(
            article
        )

        if key in seen_links:
            continue

        title = article.get(
            "title",
            ""
        )

        duplicate = False

        for existing in result:

            if similarity(
                title,
                existing.get(
                    "title",
                    ""
                )
            ) >= 0.70:

                duplicate = True
                break

        if duplicate:
            continue

        seen_links.add(key)

        result.append(
            article
        )

    print(
        f"После дедупликации: {len(result)}"
    )

    return result


# =========================================================
# ОЦЕНКА НОВОСТИ
# =========================================================

def topic_score(article):

    text = normalize(
        article.get(
            "title",
            ""
        )
        + " "
        + article.get(
            "description",
            ""
        )
    )

    score = 0

    # Тематические совпадения
    for word in TOPIC_WORDS:

        if word in text:
            score += 1

    # Свежесть
    age = age_hours(
        article.get(
            "published"
        )
    )

    if age <= 3:
        score += 10

    elif age <= 6:
        score += 8

    elif age <= 12:
        score += 6

    elif age <= 24:
        score += 4

    elif age <= 48:
        score += 2

    # Приоритет источников
    source = normalize(
        article.get(
            "source",
            ""
        )
    )

    if "ведомости" in source:
        score += 5

    elif "цб рф" in source:
        score += 5

    elif "rb.ru" in source:
        score += 4

    return score


def select_articles(
    articles,
    posted
):

    posted_set = set(
        posted
    )

    candidates = []

    for article in articles:

        key = article_key(
            article
        )

        if key in posted_set:
            continue

        candidates.append(
            article
        )

    candidates.sort(
        key=topic_score,
        reverse=True
    )

    print(
        f"Новых кандидатов: {len(candidates)}"
    )

    return candidates[
        :MAX_POSTS_PER_RUN
    ]


# =========================================================
# ЗАГОЛОВОК
# =========================================================

def clean_title(title):

    title = clean_text(
        title
    )

    # Удаляем название источника в конце
    title = re.sub(
        r"\s+[—–-]\s+(Ведомости|РБК|RB\.RU|ЦБ РФ)\s*$",
        "",
        title,
        flags=re.I
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    return title


# =========================================================
# КАРТИНКА
# =========================================================

def find_image(url):

    response = fetch(
        url,
        timeout=15
    )

    if not response:
        return None

    content_type = response.headers.get(
        "content-type",
        ""
    ).lower()

    if "text/html" not in content_type:
        return None

    text = response.text[
        :2_000_000
    ]

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if not match:
            continue

        image_url = html.unescape(
            match.group(1)
        ).strip()

        image_url = urljoin(
            url,
            image_url
        )

        image_response = fetch(
            image_url,
            timeout=20
        )

        if not image_response:
            continue

        image_type = image_response.headers.get(
            "content-type",
            ""
        ).lower()

        if not image_type.startswith(
            "image/"
        ):
            continue

        if len(
            image_response.content
        ) > MAX_IMAGE_SIZE:

            continue

        return image_response.content

    return None


# =========================================================
# TELEGRAM
# =========================================================

def telegram_api(method):

    return (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )


def check_telegram():

    print("\n========== TELEGRAM ==========")

    try:

        response = requests.get(
            telegram_api("getMe"),
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("ok"):

            raise RuntimeError(
                data
            )

        bot = data.get(
            "result",
            {}
        )

        print(
            f"Бот подключен: "
            f"@{bot.get('username')}"
        )

        return True

    except Exception as e:

        print(
            f"Ошибка Telegram: {e}"
        )

        return False


def send_message(text):

    response = requests.post(
        telegram_api(
            "sendMessage"
        ),
        json={
            "chat_id": CHANNEL,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            data
        )

    return data


def send_photo(
    photo_bytes,
    caption
):

    response = requests.post(
        telegram_api(
            "sendPhoto"
        ),
        data={
            "chat_id": CHANNEL,
            "caption": caption,
            "parse_mode": "HTML",
        },
        files={
            "photo": (
                "news.jpg",
                photo_bytes,
                "image/jpeg"
            ),
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            data
        )

    return data


# =========================================================
# ПОСТ
# =========================================================

def build_post(article):

    title = clean_title(
        article.get(
            "title",
            "Новость"
        )
    )

    source = clean_text(
        article.get(
            "source",
            "Источник"
        )
    )

    link = normalize_link(
        article.get(
            "link",
            ""
        )
    )

    title = escape_html(
        title
    )

    source = escape_html(
        source
    )

    link = escape_html(
        link
    )

    return (
        f"📰 <b>{title}</b>\n\n"
        f"Источник: {source}\n"
        f'🔗 <a href="{link}">'
        f"Читать источник"
        f"</a>"
    )


# =========================================================
# ПРОВЕРКА
# =========================================================

def quality_check(
    article,
    post
):

    if not article.get(
        "title"
    ):
        return False

    if not article.get(
        "link"
    ):
        return False

    if not is_russian(
        article.get(
            "title",
            ""
        )
    ):
        return False

    if len(post) > 4000:
        return False

    return True


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=========================================="
    )

    print(
        "МРК [БИЗНЕС НОВОСТИ] — VERSION 6.2"
    )

    print(
        "=========================================="
    )

    # Проверяем токен
    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не задан."
        )

    if not CHANNEL:

        raise RuntimeError(
            "CHANNEL не задан."
        )

    print(
        f"Канал: {CHANNEL}"
    )

    print(
        f"Максимум постов: "
        f"{MAX_POSTS_PER_RUN}"
    )

    print(
        f"Возраст новости: "
        f"{MAX_NEWS_AGE_HOURS} часов"
    )

    # Проверяем Telegram
    if not check_telegram():

        raise RuntimeError(
            "Telegram API недоступен."
        )

    # Загружаем историю
    posted = load_posted()

    print(
        f"Уже опубликовано в истории: "
        f"{len(posted)}"
    )

    # Получаем новости
    articles = fetch_all_feeds()

    print(
        "\n=========================================="
    )

    print(
        f"Всего подходящих новостей: "
        f"{len(articles)}"
    )

    print(
        "=========================================="
    )

    if not articles:

        print(
            "Подходящих новостей нет."
        )

        return

    # Дубли
    articles = remove_duplicates(
        articles
    )

    # Выбор
    selected = select_articles(
        articles,
        posted
    )

    print(
        f"К публикации: "
        f"{len(selected)}"
    )

    if not selected:

        print(
            "Все найденные новости уже публиковались."
        )

        return

    # Публикация
    for article in selected:

        title = clean_text(
            article.get(
                "title",
                ""
            )
        )

        link = normalize_link(
            article.get(
                "link",
                ""
            )
        )

        source = clean_text(
            article.get(
                "source",
                ""
            )
        )

        print(
            "\n------------------------------------------"
        )

        print(
            f"Заголовок: {title}"
        )

        print(
            f"Источник: {source}"
        )

        print(
            f"Ссылка: {link}"
        )

        post = build_post(
            article
        )

        if not quality_check(
            article,
            post
        ):

            print(
                "Пропуск: quality check"
            )

            continue

        try:

            print(
                "Ищу изображение..."
            )

            image = find_image(
                link
            )

            if image:

                print(
                    "Изображение найдено."
                )

                send_photo(
                    image,
                    post
                )

                print(
                    "✅ Опубликовано с изображением."
                )

            else:

                print(
                    "Изображение не найдено."
                )

                send_message(
                    post
                )

                print(
                    "✅ Опубликовано без изображения."
                )

            # Записываем только после успешной публикации
            posted.append(
                article_key(
                    article
                )
            )

            save_posted(
                posted
            )

        except Exception as e:

            print(
                "❌ ОШИБКА ПУБЛИКАЦИИ:"
            )

            print(
                repr(e)
            )

    print(
        "\n=========================================="
    )

    print(
        "ГОТОВО."
    )

    print(
        "=========================================="
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
