import os
import re
import json
import html
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import requests
from PIL import Image, ImageDraw, ImageFont


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

MAX_NEWS_AGE_HOURS = 48
POSTED_FILE = "posted.json"
STORY_FILE = "story_today.png"
LOGO_FILE = "mrk_logo.png"

RSS_FEEDS = [
    ("Ведомости — Бизнес", "https://www.vedomosti.ru/rss/rubric/business"),
    ("Ведомости — Экономика", "https://www.vedomosti.ru/rss/rubric/economics"),
    ("Ведомости — Технологии", "https://www.vedomosti.ru/rss/rubric/technology"),
    ("Ведомости — Предпринимательство", "https://www.vedomosti.ru/rss/rubric/management/entrepreneurship"),
    ("Ведомости — Финансы", "https://www.vedomosti.ru/rss/rubric/finance"),
    ("ЦБ РФ — Новости", "https://www.cbr.ru/rss/RssNews"),
    ("ЦБ РФ — Пресс-релизы", "https://www.cbr.ru/rss/RssPress"),
    ("RB.RU — IT", "https://rb.ru/feeds/tag/it/"),
    ("RB.RU — AI", "https://rb.ru/feeds/tag/ai/"),
    ("RB.RU — E-commerce", "https://rb.ru/feeds/tag/ecommerce/"),
]

TOPIC_WORDS = {
    "бизнес","компания","компании","предприниматель","предприниматели",
    "предприятие","предприятия","инвестиции","инвестор","инвесторы",
    "сделка","сделки","стартап","стартапы","мсп","рынок","рынки",
    "экономика","экономический","ввп","инфляция","ставка","ключевая ставка",
    "центробанк","центральный банк","банк россии","минфин","бюджет",
    "налоги","налог","ндс","рубль","рубля","рублей","кредит","кредиты",
    "ипотека","финансирование","технологии","технология","ит","айти",
    "цифровизация","цифровой","искусственный интеллект","ии","нейросеть",
    "нейросети","машинное обучение","робот","роботы","робототехника",
    "разработка","разработчик","приложение","приложения","сервис","сервисы",
    "облако","облачный","дата-центр","кибербезопасность","телеком",
    "микросхема","микросхемы","процессор","квантовый","беспилотник",
    "экспорт","импорт","логистика","ритейл","торговля","производство",
    "промышленность","выручка","прибыль","убыток","зарплата","цены",
}

LOW_VALUE_WORDS = {
    "спорт","футбол","хоккей","матч","кино","музыка","шоу",
    "певец","певица","актер","актриса","гороскоп","рецепт","погода",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 Chrome/131.0 Safari/537.36"
}


def clean_text(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize(text):
    return clean_text(text).lower()


def is_russian(text):
    cyr = len(re.findall(r"[а-яё]", clean_text(text).lower()))
    return cyr >= 3


def parse_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None


def age_hours(value):
    dt = parse_date(value)
    if not dt:
        return 0
    return max(0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)


def fetch(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[HTTP ERROR] {url}: {e}")
        return None


def parse_rss(xml_text, source):
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"[RSS ERROR] {source}: {e}")
        return articles

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for item in items:
        title = clean_text(item.findtext("title", ""))
        description = clean_text(item.findtext("description", ""))
        link = clean_text(item.findtext("link", ""))
        pub_date = clean_text(item.findtext("pubDate", ""))

        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                link = atom_link.attrib.get("href", "")

        if not pub_date:
            for child in item:
                tag = child.tag.lower()
                if tag.endswith("date") or tag.endswith("updated") or tag.endswith("published"):
                    pub_date = clean_text(child.text or "")
                    if pub_date:
                        break

        if title and link:
            articles.append({
                "title": title,
                "description": description,
                "link": link,
                "published": pub_date,
                "source": source,
            })
    return articles


def relevant(article):
    title = article["title"]
    text = normalize(title + " " + article.get("description", ""))

    if not is_russian(title):
        return False

    hits = sum(1 for w in TOPIC_WORDS if w in text)
    if hits == 0:
        return False

    low_hits = sum(1 for w in LOW_VALUE_WORDS if w in text)
    if low_hits and hits < 2:
        return False

    return True


def load_posted():
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-2000:], f, ensure_ascii=False, indent=2)


def article_key(article):
    return article["link"].split("#")[0].strip()


def similarity(a, b):
    wa = set(re.findall(r"[а-яёa-z0-9]{4,}", normalize(a)))
    wb = set(re.findall(r"[а-яёa-z0-9]{4,}", normalize(b)))
    if not wa or not wb:
        return 0
    return len(wa & wb) / len(wa | wb)


def collect_news():
    result = []
    for source, url in RSS_FEEDS:
        print(f"[RSS] {source}")
        r = fetch(url)
        if not r:
            continue

        items = parse_rss(r.text, source)
        accepted = 0

        for article in items:
            if age_hours(article.get("published")) > MAX_NEWS_AGE_HOURS:
                continue
            if relevant(article):
                result.append(article)
                accepted += 1

        print(f"  найдено: {len(items)}, подходит: {accepted}")

    # Убираем повторы
    result.sort(
        key=lambda x: parse_date(x.get("published")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    unique = []
    seen = set()

    for article in result:
        key = article_key(article)
        if key in seen:
            continue
        if any(similarity(article["title"], x["title"]) >= 0.70 for x in unique):
            continue
        seen.add(key)
        unique.append(article)

    return unique


def score(article):
    text = normalize(article["title"] + " " + article.get("description", ""))
    s = sum(1 for w in TOPIC_WORDS if w in text)

    age = age_hours(article.get("published"))
    if age <= 3:
        s += 10
    elif age <= 6:
        s += 8
    elif age <= 12:
        s += 6
    elif age <= 24:
        s += 4
    else:
        s += 2

    if "ведомости" in normalize(article["source"]) or "цб рф" in normalize(article["source"]):
        s += 5

    return s


def choose_story_article():
    posted = set(load_posted())
    news = collect_news()
    candidates = [x for x in news if article_key(x) not in posted]

    if not candidates:
        print("Новых новостей для сторис нет.")
        return None

    candidates.sort(key=score, reverse=True)
    return candidates[0]


def fonts():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    bold_path = next((p for p in candidates if os.path.exists(p)), None)
    regular_path = next((p for p in regular if os.path.exists(p)), None)

    if not bold_path or not regular_path:
        raise RuntimeError("В системе не найден шрифт с поддержкой кириллицы.")

    return bold_path, regular_path


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test = word if not line else line + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines


def make_story(article):
    W, H = 1080, 1920

    # Строгий фирменный фон
    img = Image.new("RGB", (W, H), (8, 20, 35))
    draw = ImageDraw.Draw(img)

    # Светлый верхний градиент
    for y in range(0, 650):
        t = y / 650
        c = (
            int(220 - 150 * t),
            int(230 - 155 * t),
            int(235 - 160 * t),
        )
        draw.line((0, y, W, y), fill=c)

    bold_path, regular_path = fonts()

    logo = None
    if os.path.exists(LOGO_FILE):
        try:
            logo = Image.open(LOGO_FILE).convert("RGBA")
            logo.thumbnail((260, 260))
            img.alpha_composite(logo, (60, 55)) if img.mode == "RGBA" else img.paste(logo, (60, 55), logo)
        except Exception as e:
            print(f"Логотип не загружен: {e}")

    title_font = ImageFont.truetype(bold_path, 76)
    headline_font = ImageFont.truetype(bold_path, 64)
    body_font = ImageFont.truetype(regular_path, 42)
    small_font = ImageFont.truetype(regular_path, 30)
    label_font = ImageFont.truetype(bold_path, 34)

    # Шапка
    draw.text((360, 85), "МРК", font=title_font, fill=(10, 25, 45))
    draw.text((360, 170), "БИЗНЕС НОВОСТИ", font=label_font, fill=(35, 86, 150))

    draw.line((60, 340, 1020, 340), fill=(100, 125, 150), width=3)

    # Тип сторис
    weekday = datetime.now().weekday()
    labels = [
        "БИЗНЕС ЗА МИНУТУ",
        "ЦИФРА ДНЯ",
        "ГЛАВНАЯ НОВОСТЬ",
        "КОМПАНИЯ ДНЯ",
        "ГЛАВНОЕ ЗА НЕДЕЛЮ",
        "А ТЫ ЗНАЛ?",
        "ПРОГНОЗ НЕДЕЛИ",
    ]
    label = labels[weekday]

    draw.rounded_rectangle(
        (60, 390, 510, 455),
        radius=25,
        fill=(12, 30, 50),
    )
    draw.text((85, 404), label, font=small_font, fill=(245, 247, 250))

    # Заголовок новости
    title = clean_text(article["title"])
    if len(title) > 150:
        title = title[:147].rsplit(" ", 1)[0] + "..."

    lines = wrap_text(
        draw,
        title,
        headline_font,
        900,
    )

    y = 540
    for line in lines[:6]:
        draw.text(
            (60, y),
            line,
            font=headline_font,
            fill=(245, 247, 250),
        )
        y += 80

    # Источник
    y += 35
    draw.text(
        (60, y),
        article["source"],
        font=body_font,
        fill=(120, 185, 245),
    )

    # CTA
    draw.rounded_rectangle(
        (60, 1480, 1020, 1650),
        radius=35,
        outline=(70, 150, 230),
        width=3,
    )

    draw.text(
        (105, 1520),
        "Подробнее о событии",
        font=body_font,
        fill=(245, 247, 250),
    )
    draw.text(
        (105, 1585),
        "Читайте в канале → @etomrk",
        font=small_font,
        fill=(120, 185, 245),
    )

    draw.line(
        (60, 1740, 1020, 1740),
        fill=(65, 90, 115),
        width=2,
    )

    draw.text(
        (60, 1780),
        "БИЗНЕС • ЭКОНОМИКА • ТЕХНОЛОГИИ",
        font=small_font,
        fill=(190, 200, 210),
    )

    draw.text(
        (60, 1835),
        "РОССИЯ",
        font=small_font,
        fill=(100, 160, 220),
    )

    img.save(STORY_FILE, quality=95)
    return STORY_FILE


def telegram(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    r = requests.post(url, data=data or {}, files=files, timeout=60)
    r.raise_for_status()
    result = r.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", str(result)))
    return result


def send_story_to_admin(path, article):
    if not ADMIN_CHAT_ID:
        raise RuntimeError("Не задан ADMIN_CHAT_ID.")

    caption = (
        "📲 <b>Готова сторис МРК</b>\n\n"
        f"<b>{html.escape(article['title'])}</b>\n\n"
        "Нажми «Добавить в историю» и опубликуй её в канале."
    )

    with open(path, "rb") as f:
        telegram(
            "sendPhoto",
            data={
                "chat_id": ADMIN_CHAT_ID,
                "caption": caption[:1024],
                "parse_mode": "HTML",
            },
            files={
                "photo": ("story.png", f, "image/png")
            },
        )


def main():
    print("==========================================")
    print("МРК 6.3 — АВТОМАТИЧЕСКИЕ СТОРИС")
    print("==========================================")

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан.")

    if not ADMIN_CHAT_ID:
        raise RuntimeError("ADMIN_CHAT_ID не задан.")

    article = choose_story_article()

    if not article:
        return

    print(f"\nВыбрана новость:\n{article['title']}")
    print(f"Источник: {article['source']}")

    path = make_story(article)

    send_story_to_admin(path, article)

    # Сохраняем только после успешной отправки
    posted = load_posted()
    posted.append(article_key(article))
    save_posted(posted)

    print("\n✅ Сторис создана и отправлена.")
    print("Файл:", path)


if __name__ == "__main__":
    main()
