import os
import re
import json
import html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")

# Сколько новостей публиковать за один запуск
MAX_POSTS_PER_RUN = 2

# Берём новости не старше этого количества часов
MAX_NEWS_AGE_HOURS = 48

# Не публиковать один и тот же материал повторно
POSTED_FILE = "posted.json"

# Максимальный размер изображения
MAX_IMAGE_SIZE = 9 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# =========================================================
# РОССИЙСКИЕ RSS-ИСТОЧНИКИ
# =========================================================
#
# Используются прямые RSS-ленты российских источников.
# Никаких английских Google News / Reuters / USA feeds.
#
# Ведомости официально публикуют RSS для бизнеса, экономики,
# технологий и предпринимательства.
#
# ЦБ РФ — официальный российский источник экономических
# и финансовых новостей.
#
# RB.RU — российское деловое/технологическое издание.
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
# ФИЛЬТР ТЕМАТИКИ
# =========================================================

# Материал должен относиться хотя бы к одной из четырёх
# нужных тем: бизнес, экономика, предпринимательство, технологии.

TOPIC_WORDS = {
    # Бизнес
    "бизнес", "компания", "компании", "предприниматель", "предприниматели",
    "предприятие", "предприятия", "корпорация", "корпоративный",
    "выручка", "прибыль", "убыток", "инвестиции", "инвестор",
    "инвесторы", "сделка", "сделки", "слияние", "поглощение",
    "стартап", "стартапы", "мсп", "малый бизнес", "средний бизнес",
    "ритейл", "торговля", "производство", "промышленность",
    "экспорт", "импорт", "логистика", "рынок",

    # Экономика
    "экономика", "экономический", "ввп", "инфляция", "дефляция",
    "ставка", "ключевая ставка", "центробанк", "банк россии",
    "минфин", "бюджет", "налоги", "налог", "ндс", "рубль",
    "рубля", "рублей", "занятость", "безработица", "зарплата",
    "цены", "доходы", "расходы", "кредит", "кредиты", "ипотека",
    "денежно-кредитная", "денежная политика",

    # Предпринимательство
    "предпринимательство", "ип", "самозанятые", "самозанятый",
    "бизнесмен", "бизнесмены", "бизнес-проект", "франшиза",
    "франшизы", "венчур", "венчурный капитал", "финансирование",
    "грант", "гранты", "акселератор", "инкубатор",

    # Технологии
    "технологии", "технология", "ит", "айти", "цифровизация",
    "цифровой", "искусственный интеллект", "ии", "нейросеть",
    "нейросети", "машинное обучение", "робот", "роботы",
    "робототехника", "программное обеспечение", "по",
    "разработка", "разработчик", "разработчики", "приложение",
    "приложения", "сервис", "сервисы", "облако", "облачный",
    "дата-центр", "дата-центры", "кибербезопасность", "телеком",
    "связь", "микросхема", "микросхемы", "процессор",
    "квантовый", "квантовые", "биотехнологии", "беспилотник",
    "беспилотники",
}

# Материал должен иметь российский контекст.
# Это защищает канал от случайных мировых новостей из RSS.
RUSSIA_WORDS = {
    "россия", "россии", "россию", "российский", "российская",
    "российские", "российского", "рф", "москва", "московская",
    "санкт-петербург", "петербург", "питер", "казань",
    "новосибирск", "екатеринбург", "нижний новгород", "краснодар",
    "ростов", "владивосток", "хабаровск", "сочи", "самара",
    "татарстан", "дагестан", "чечня", "урал", "сибирь",
    "дальний восток", "крым", "рубль", "рубля", "рублей",
    "мосбиржа", "московская биржа", "сбер", "сбербанк", "втб",
    "газпром", "роснефть", "лукойл", "яндекс", "озон",
    "ozon", "wildberries", "авито", "вк", "ростелеком",
    "мтс", "мегафон", "билайн", "тинькофф", "альфа-банк",
    "совкомбанк", "новатэк", "русал", "северсталь",
    "магнит", "пятерочка", "x5", "ржд", "аэрофлот",
    "росатом", "ростех", "роскосмос", "яндекс", "касперский",
    "1с", "аск", "минфин", "минэкономразвития", "минцифры",
    "центробанк", "банк россии", "фнс", "правительство россии",
    "госдума", "федеральная налоговая служба",
}

LOW_VALUE_WORDS = {
    "спорт", "футбол", "хоккей", "матч", "кино", "музыка",
    "шоу", "певец", "певица", "актер", "актриса", "знаменитость",
    "гороскоп", "рецепт", "погода", "происшествие", "криминал",
}


# =========================================================
# БАЗОВЫЕ ФУНКЦИИ
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

    for word in words:
        if word in text:
            return True

    return False


def article_is_relevant(article):
    title = article.get("title", "")
    description = article.get("description", "")
    text = normalize(title + " " + description)

    # Только русскоязычные материалы.
    if not is_russian(title):
        return False

    # Только одна из нужных тем.
    if not contains_any(text, TOPIC_WORDS):
        return False

    # Для российского канала нужен российский контекст.
    if not contains_any(text, RUSSIA_WORDS):
        return False

    # Отсекаем очевидный оффтоп.
    if contains_any(text, LOW_VALUE_WORDS):
        # Не отбрасываем материал, если в нём одновременно
        # явно есть бизнес/экономика/технологии и Россия.
        # Здесь только мягкая проверка.
        topic_hits = sum(1 for word in TOPIC_WORDS if word in text)
        if topic_hits < 2:
            return False

    return True


# =========================================================
# ИСТОРИЯ
# =========================================================

def load_json_file(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_posted():
    data = load_json_file(POSTED_FILE, [])

    if not isinstance(data, list):
        return []

    return data


def save_posted(data):
    save_json_file(POSTED_FILE, data[-2000:])


# =========================================================
# ДАТЫ
# =========================================================

def parse_date(value):
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def age_hours(value):
    dt = parse_date(value)

    if not dt:
        # Если источник не дал дату, материал лучше не брать.
        return 999

    now = datetime.now(timezone.utc)
    return max(0, (now - dt).total_seconds() / 3600)


# =========================================================
# HTTP
# =========================================================

def fetch(url, timeout=20):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
        )

        response.raise_for_status()
        return response

    except Exception as e:
        print(f"HTTP error: {url} -> {e}")
        return None


# =========================================================
# RSS
# =========================================================

def parse_rss(xml_text, source):
    articles = []

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"RSS parse error ({source}): {e}")
        return articles

    # RSS 2.0
    items = root.findall(".//item")

    for item in items:
        title = clean_text(item.findtext("title", ""))
        description = clean_text(item.findtext("description", ""))
        link = clean_text(item.findtext("link", ""))
        pub_date = clean_text(item.findtext("pubDate", ""))

        # Некоторые RSS используют dc:date.
        if not pub_date:
            for child in item:
                if child.tag.endswith("date"):
                    pub_date = clean_text(child.text or "")
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

    for source, url in RSS_FEEDS:
        print(f"RSS: {source}")

        response = fetch(url)

        if not response:
            continue

        articles = parse_rss(response.text, source)

        print(f"  найдено: {len(articles)}")

        for article in articles:
            if age_hours(article.get("published")) > MAX_NEWS_AGE_HOURS:
                continue

            if not article_is_relevant(article):
                continue

            all_articles.append(article)

    return all_articles


# =========================================================
# ДЕДУПЛИКАЦИЯ
# =========================================================

def normalize_link(link):
    link = clean_text(link)

    try:
        parsed = urlparse(link)

        # Убираем стандартные tracking-параметры.
        query_parts = []

        for part in parsed.query.split("&"):
            if not part:
                continue

            key = part.split("=", 1)[0].lower()

            if key.startswith("utm_"):
                continue

            if key in {"from", "ref", "source", "yclid", "fbclid"}:
                continue

            query_parts.append(part)

        query = "&".join(query_parts)

        return parsed._replace(query=query, fragment="").geturl()

    except Exception:
        return link


def article_key(article):
    link = normalize_link(article.get("link", ""))

    if link:
        return link

    return normalize(article.get("title", ""))


def important_words(text):
    words = re.findall(r"[а-яёa-z0-9]{4,}", normalize(text))

    stop_words = {
        "бизнес", "компания", "компании", "россия", "российский",
        "новости", "которые", "который", "которых", "также",
        "после", "будет", "будут", "этот", "этого", "своего",
        "свои", "может", "могут", "стало", "стали",
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

    intersection = len(a & b)
    union = len(a | b)

    return intersection / union


def remove_duplicates(articles):
    result = []
    seen_links = set()

    # Сначала сортируем от новых к старым.
    articles = sorted(
        articles,
        key=lambda x: parse_date(x.get("published")) or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )

    for article in articles:
        key = article_key(article)

        if key in seen_links:
            continue

        title = article.get("title", "")

        duplicate = False

        for existing in result:
            if similarity(title, existing.get("title", "")) >= 0.70:
                duplicate = True
                break

        if duplicate:
            continue

        seen_links.add(key)
        result.append(article)

    return result


# =========================================================
# ВЫБОР НОВОСТЕЙ
# =========================================================

def topic_score(article):
    text = normalize(
        article.get("title", "") + " " + article.get("description", "")
    )

    score = 0

    # Чем больше прямых совпадений с нужными темами,
    # тем выше материал в очереди.
    for word in TOPIC_WORDS:
        if word in text:
            score += 1

    # Российский контекст.
    for word in RUSSIA_WORDS:
        if word in text:
            score += 2

    # Свежесть.
    age = age_hours(article.get("published"))

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

    # Приоритет прямым деловым источникам.
    source = normalize(article.get("source", ""))

    if "ведомости" in source:
        score += 5
    elif "цб рф" in source:
        score += 5
    elif "rb.ru" in source:
        score += 4

    return score


def select_articles(articles, posted):
    posted_set = set(posted)

    candidates = []

    for article in articles:
        key = article_key(article)

        if key in posted_set:
            continue

        candidates.append(article)

    candidates.sort(
        key=topic_score,
        reverse=True,
    )

    return candidates[:MAX_POSTS_PER_RUN]


# =========================================================
# ЗАГОЛОВОК
# =========================================================

def clean_title(title):
    title = clean_text(title)

    # Убираем хвосты вида "— Ведомости".
    title = re.sub(
        r"\s+[—-]\s+(Ведомости|РБК|RB\.RU|ЦБ РФ)\s*$",
        "",
        title,
        flags=re.I,
    )

    # Убираем лишние пробелы.
    title = re.sub(r"\s+", " ", title).strip()

    return title


# =========================================================
# ИЗОБРАЖЕНИЕ
# =========================================================

def find_image(url):
    """
    Пытаемся взять og:image со страницы источника.
    Если изображение недоступно, новость всё равно публикуется
    обычным текстом.
    """

    response = fetch(url, timeout=15)

    if not response:
        return None

    content_type = response.headers.get("content-type", "").lower()

    if "text/html" not in content_type:
        return None

    text = response.text[:2_000_000]

    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)

        if not match:
            continue

        image_url = html.unescape(match.group(1)).strip()

        if image_url.startswith("//"):
            image_url = "https:" + image_url

        if image_url.startswith("/"):
            parsed = urlparse(url)
            image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"

        if not image_url.startswith(("http://", "https://")):
            continue

        image_response = fetch(image_url, timeout=20)

        if not image_response:
            continue

        image_type = image_response.headers.get("content-type", "").lower()

        if not image_type.startswith("image/"):
            continue

        if len(image_response.content) > MAX_IMAGE_SIZE:
            continue

        return image_response.content

    return None


# =========================================================
# TELEGRAM
# =========================================================

def telegram_api(method):
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def send_message(text):
    response = requests.post(
        telegram_api("sendMessage"),
        json={
            "chat_id": CHANNEL,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def send_photo(photo_bytes, caption):
    response = requests.post(
        telegram_api("sendPhoto"),
        data={
            "chat_id": CHANNEL,
            "caption": caption,
            "parse_mode": "HTML",
        },
        files={
            "photo": ("news.jpg", photo_bytes, "image/jpeg"),
        },
        timeout=60,
    )

    response.raise_for_status()
    return response.json()


# =========================================================
# ФОРМАТ ПОСТА
# =========================================================
#
# ВАЖНО:
# Здесь специально НЕТ:
# - "Почему это важно"
# - категории
# - рынка
# - краткого описания
# - анализа
# - хэштегов
# - котировок
# - курсов валют
# - перевода через сторонний сервис
#
# Только:
# заголовок
# источник
# ссылка
# =========================================================

def build_post(article):
    title = clean_title(article.get("title", "Новость"))
    source = clean_text(article.get("source", "Источник"))
    link = normalize_link(article.get("link", ""))

    title = escape_html(title)
    source = escape_html(source)
    link = escape_html(link)

    return (
        f"📰 <b>{title}</b>\n\n"
        f"Источник: {source}\n"
        f"🔗 <a href=\"{link}\">Читать источник</a>"
    )


# =========================================================
# ПРОВЕРКА
# =========================================================

def quality_check(article, post):
    if not article.get("title"):
        return False

    if not article.get("link"):
        return False

    if not is_russian(article.get("title", "")):
        return False

    if len(post) > 4000:
        return False

    return True


# =========================================================
# ОСНОВНАЯ ЛОГИКА
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Добавь секрет BOT_TOKEN в GitHub Actions."
        )

    if not CHANNEL:
        raise RuntimeError(
            "Не задан CHANNEL."
        )

    print("==========================================")
    print("МРК [БИЗНЕС НОВОСТИ] — запуск")
    print("Темы: бизнес / экономика / предпринимательство / технологии")
    print("Источники: российские")
    print("==========================================")

    posted = load_posted()

    articles = fetch_all_feeds()

    print(f"После фильтра: {len(articles)}")

    articles = remove_duplicates(articles)

    print(f"После дедупликации: {len(articles)}")

    selected = select_articles(articles, posted)

    print(f"К публикации: {len(selected)}")

    if not selected:
        print("Новых подходящих новостей нет.")
        return

    for article in selected:
        post = build_post(article)

        if not quality_check(article, post):
            print("Пропуск: не прошёл quality check")
            continue

        title = clean_text(article.get("title", ""))
        link = normalize_link(article.get("link", ""))

        print("------------------------------------------")
        print(title)
        print(article.get("source", ""))
        print(link)

        try:
            # Изображение необязательно.
            # Если найти не удалось — отправляем обычный пост.
            image = find_image(link)

            if image:
                send_photo(image, post)
                print("Опубликовано с изображением.")
            else:
                send_message(post)
                print("Опубликовано без изображения.")

            posted.append(article_key(article))
            save_posted(posted)

        except Exception as e:
            print(f"Ошибка публикации: {e}")

    print("Готово.")


if __name__ == "__main__":
    main()
