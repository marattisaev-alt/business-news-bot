# -*- coding: utf-8 -*-
"""
МРК | БЕЗ ФИЛЬТРОВ — бесплатный развлекательный RSS-бот.
Версия 11.0:
- фильтрует материалы по тематическим ключевым словам;
- исключает точные и похожие заголовки;
- хранит историю публикаций в posted.json;
- публикует фотографию, если RSS содержит прямую ссылку на изображение;
- при неудаче отправки фото пробует отправить текст;
- ведёт понятные логи для GitHub Actions.

Важно: RSS не даёт гарантии реальной вирусности публикации. Бот ранжирует
материалы по признакам в заголовке и описании, а не по статистике соцсетей.
"""

import os
import re
import json
import time
import html
import hashlib
import logging
import difflib
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

VERSION = "11.0"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL = os.getenv("CHANNEL", "").strip()
MAX_POSTS_PER_DAY = max(1, int(os.getenv("MAX_POSTS_PER_DAY", "6")))
MAX_POSTS_PER_RUN = max(1, int(os.getenv("MAX_POSTS_PER_RUN", "1")))
MAX_ITEM_AGE_HOURS = max(1, int(os.getenv("MAX_ITEM_AGE_HOURS", "36")))
POSTED_FILE = "posted.json"
STATE_FILE = "state.json"
TIMEOUT = 20
MAX_HISTORY = 5000
SIMILARITY_THRESHOLD = 0.88

RSS_FEEDS = [
    ("Афиша Daily", "https://daily.afisha.ru/export/rss/google_newsstand/", "culture"),
    ("Onedio — Развлечение", "https://onedio.ru/Publisher/publisher-razvlechenie.rss", "viral"),
    ("Fishki.net", "https://fishki.net/rss/", "humor"),
    ("Pikabu — популярное", "https://pikabu.ru/xmlfeeds.php?cmd=popular", "viral"),
    ("Anekdot.ru — юмор", "https://www.anekdot.ru/rss/export_j_burning.xml", "humor"),
    ("Meduza — все материалы", "https://meduza.io/rss/all", "viral"),
]

CATEGORY_RULES = {
    "😂 ЮМОР И МЕМЫ": [
        "мем", "смешн", "юмор", "шутк", "прикол", "комикс", "сарказм",
        "жиза", "забавно", "анекдот", "смех", "котик", "кот", "собак",
        "ржач", "угар", "смешно"
    ],
    "🔥 ВИРУСНОЕ": [
        "вирусн", "завирус", "обсуждают", "разлетел", "соцсет", "интернет",
        "ролик", "видео", "тренд", "флешмоб", "пользовател", "комментарии",
        "в сети", "пост набрал", "просмотров", "репост"
    ],
    "👀 БЛОГЕРЫ И ЗВЁЗДЫ": [
        "блогер", "инфлюенсер", "стример", "ютуб", "youtube", "тикток",
        "tiktok", "телеграм-канал", "артист", "актёр", "актер", "певиц",
        "звезд", "шоу", "селебрити", "инстаграм", "instagram"
    ],
    "🤯 НЕОБЫЧНЫЕ ИСТОРИИ": [
        "необыч", "странн", "курьез", "курьёз", "удивитель", "неожидан",
        "случай", "история", "рекорд", "животн", "уморитель", "невероят",
        "загадоч", "чудес", "впервые", "потерял", "нашёл", "нашел"
    ],
    "🎬 КУЛЬТУРА И ПОП-КУЛЬТУРА": [
        "кино", "фильм", "сериал", "музык", "премьера", "альбом", "актёр",
        "актер", "певец", "певица", "шоу", "концерт", "мультфильм",
        "трейлер", "кинопрокат"
    ],
}

BLOCK_TERMS = [
    "бизнес", "экономик", "бирж", "акци", "инвестици", "кредит", "налог",
    "банк россии", "ставка цб", "политик", "выборы", "государственная дума",
    "военн", "обстрел", "теракт", "погиб", "погибли", "убийств", "насили",
    "казино", "ставки на спорт", "эротика", "порно", "шок-контент",
    "жестокое обращение", "суицид", "оружие", "взрыв"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MRKEntertainmentBot/11.0; +https://github.com/marattisaev-alt/business-news-bot)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def clean(value):
    value = html.unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value):
    value = clean(value)
    if not value:
        return 0
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        return 0


def local_name(tag):
    return tag.rsplit("}", 1)[-1].lower()


def first_nonempty(fields, *names):
    for name in names:
        value = fields.get(name)
        if value:
            return value
    return ""


def parse_feed(content, source, feed_kind):
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logging.warning("Не удалось разобрать RSS %s: %s", source, exc)
        return []

    items = []
    for node in root.iter():
        if local_name(node.tag) not in ("item", "entry"):
            continue

        fields = {}
        image_url = ""

        for child in list(node):
            name = local_name(child.tag)
            child_text = "".join(child.itertext()).strip()

            if name == "link":
                href = child.attrib.get("href", "").strip()
                rel = child.attrib.get("rel", "")
                if href and (not rel or rel == "alternate"):
                    fields.setdefault("link", href)
                elif child_text:
                    fields.setdefault("link", child_text)
            elif child_text and name not in fields:
                fields[name] = child_text

            # RSS media:thumbnail / media:content / enclosure
            candidate = child.attrib.get("url", "").strip()
            media_type = child.attrib.get("type", "").lower()
            if name in ("thumbnail", "content", "enclosure") and candidate.startswith("https://"):
                if not media_type or media_type.startswith("image/"):
                    image_url = candidate

            # Some feeds put the image in an HTML description.
            if name in ("description", "summary", "encoded", "content") and not image_url:
                match = re.search(r"""<img[^>]+src=["'](https://[^"']+)["']""", child_text, re.I)
                if match:
                    image_url = html.unescape(match.group(1))

        title = clean(first_nonempty(fields, "title"))
        link = clean(first_nonempty(fields, "link", "guid", "id"))
        description = clean(first_nonempty(fields, "description", "summary", "encoded", "content"))
        published = first_nonempty(fields, "pubdate", "published", "updated", "date", "dc:date")

        if title and link.startswith(("https://", "http://")):
            items.append({
                "title": title[:400],
                "description": description[:1800],
                "link": link,
                "source": source,
                "feed_kind": feed_kind,
                "published": parse_date(published),
                "image_url": image_url,
            })
    return items


def fetch(source, url, feed_kind):
    logging.info("Загружаю RSS: %s", source)
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        items = parse_feed(response.content, source, feed_kind)
        logging.info("%s: найдено материалов — %d", source, len(items))
        return items
    except Exception as exc:
        logging.warning("Ошибка RSS (%s): %s", source, exc)
        return []


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def save_json_atomic(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def load_posted_records():
    raw = load_json(POSTED_FILE, [])
    records = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and entry.get("key"):
                records.append({
                    "key": str(entry["key"]),
                    "published_at": int(entry.get("published_at", 0) or 0),
                    "title": clean(str(entry.get("title", ""))),
                    "link": str(entry.get("link", "")),
                })
            elif isinstance(entry, str):
                records.append({"key": entry, "published_at": 0, "title": "", "link": ""})
    elif isinstance(raw, dict):
        for key, value in raw.items():
            timestamp = int(value or 0) if str(value or "0").isdigit() else 0
            records.append({"key": str(key), "published_at": timestamp, "title": "", "link": ""})
    return records[-MAX_HISTORY:]


def normalized_title(title):
    title = clean(title).lower().replace("ё", "е")
    title = re.sub(r"https?://\S+", " ", title)
    title = re.sub(r"[^\w\s]", " ", title, flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def canonical_link(link):
    try:
        parsed = urlparse(link.strip())
        # Drop tracking parameters but keep the path and non-tracking query parameters.
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in ("ref", "fbclid", "gclid")]
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"),
                           "", urlencode(query), ""))
    except Exception:
        return link.strip().lower()


def item_key(item):
    raw = canonical_link(item.get("link", "")) + "|" + normalized_title(item.get("title", ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_fresh(item):
    timestamp = item.get("published", 0)
    if not timestamp:
        return True
    age_hours = (time.time() - timestamp) / 3600
    return -2 <= age_hours <= MAX_ITEM_AGE_HOURS


def classify(item):
    text = (item["title"] + " " + item.get("description", "")).lower().replace("ё", "е")
    scores = {
        category: sum(1 for term in terms if term in text)
        for category, terms in CATEGORY_RULES.items()
    }
    category, score = max(scores.items(), key=lambda pair: pair[1])
    if score:
        return category, score

    if item.get("feed_kind") == "humor":
        return "😂 ЮМОР И МЕМЫ", 1
    if item.get("feed_kind") == "culture":
        return "🎬 КУЛЬТУРА И ПОП-КУЛЬТУРА", 1
    return "🔥 ВИРУСНОЕ", 1


def score_item(item):
    text = (item["title"] + " " + item.get("description", "")).lower().replace("ё", "е")
    if any(term in text for term in BLOCK_TERMS):
        return -100, ""

    category, hits = classify(item)
    explicit_signals = any(
        term in text for terms in CATEGORY_RULES.values() for term in terms
    )
    if item.get("feed_kind") == "viral" and not explicit_signals:
        return -2, category

    score = hits * 3
    if 22 <= len(item["title"]) <= 140:
        score += 1
    if item.get("description"):
        score += 1
    if len(item["title"]) < 12:
        score -= 3
    if item.get("image_url"):
        score += 1
    if item.get("published"):
        age = max(0, (time.time() - item["published"]) / 3600)
        if age <= 6:
            score += 2
        elif age <= 18:
            score += 1
    return score, category


def is_similar_title(title, prior_titles):
    current = normalized_title(title)
    if not current:
        return True
    for old_title in prior_titles:
        old = normalized_title(old_title)
        if not old:
            continue
        if current == old:
            return True
        # Compare only titles with some length to avoid false matches on short phrases.
        if min(len(current), len(old)) >= 24:
            if difflib.SequenceMatcher(None, current, old).ratio() >= SIMILARITY_THRESHOLD:
                return True
    return False


def select_items(items, posted_records):
    selected = []
    posted_keys = {record["key"] for record in posted_records}
    prior_titles = [record.get("title", "") for record in posted_records if record.get("title")]
    seen_keys, seen_titles = set(), []

    for item in items:
        item["title"] = clean(item.get("title", ""))
        item["description"] = clean(item.get("description", ""))
        item["link"] = clean(item.get("link", ""))

        if len(item["title"]) < 12 or not item["link"].startswith(("https://", "http://")):
            continue
        if not is_fresh(item):
            continue

        key = item_key(item)
        if key in posted_keys or key in seen_keys:
            continue
        if is_similar_title(item["title"], prior_titles + seen_titles):
            continue

        score, category = score_item(item)
        if score < 1:
            continue

        item["_key"] = key
        item["_score"] = score
        item["category"] = category
        seen_keys.add(key)
        seen_titles.append(item["title"])
        selected.append(item)

    selected.sort(key=lambda item: (item["_score"], item.get("published", 0)), reverse=True)
    return selected


def telegram(method, data=None, files=None):
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data or {},
        files=files,
        timeout=TIMEOUT,
    )
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(response.text[:300])
    if not response.ok or not result.get("ok"):
        raise RuntimeError(result.get("description", f"Telegram HTTP {response.status_code}"))
    return result


def build_caption(item):
    title = html.escape(item["title"])
    category = html.escape(item["category"])
    source = html.escape(item["source"])
    link = html.escape(item["link"], quote=True)
    description = clean(item.get("description", ""))

    # Keep the caption concise; Telegram photo captions have a 1024-character limit.
    if description and normalized_title(description) not in normalized_title(item["title"]):
        description = html.escape(description[:300])
    parts = [f"🔥 <b>{title}</b>"]
    if description:
        parts.extend(["", description])
    parts.extend(["", category, "", f'📰 <a href="{link}">Источник: {source}</a>', "", "#МРКБезФильтров"])
    return "\n".join(parts)[:1000]


def publish_item(item):
    caption = build_caption(item)
    image_url = item.get("image_url", "")

    if image_url.startswith("https://"):
        try:
            # Telegram can fetch a public image URL directly. This avoids downloading large files.
            telegram("sendPhoto", {
                "chat_id": CHANNEL,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
            })
            logging.info("Опубликовано с фото: %s", item["title"])
            return
        except Exception as exc:
            logging.warning("Фото не отправлено, пробую текст (%s): %s", item["title"], exc)

    telegram("sendMessage", {
        "chat_id": CHANNEL,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })
    logging.info("Опубликовано текстом: %s", item["title"])


def daily_count(records, now_ts):
    today = datetime.fromtimestamp(now_ts, timezone.utc).date()
    count = 0
    for record in records:
        published_at = record.get("published_at", 0)
        if published_at:
            try:
                if datetime.fromtimestamp(published_at, timezone.utc).date() == today:
                    count += 1
            except (ValueError, OSError, OverflowError):
                continue
    return count


def main():
    logging.info("MRK | БЕЗ ФИЛЬТРОВ — версия %s", VERSION)
    if not BOT_TOKEN or not CHANNEL:
        raise RuntimeError("BOT_TOKEN или CHANNEL не заполнен. Проверь GitHub Secrets.")

    bot = telegram("getMe")["result"]
    logging.info("Бот подключён: @%s", bot.get("username", "unknown"))

    records = load_posted_records()
    posted_keys = {record["key"] for record in records}
    now_ts = int(time.time())
    count_today = daily_count(records, now_ts)
    remaining = MAX_POSTS_PER_DAY - count_today
    logging.info("Опубликовано сегодня: %d; дневной лимит: %d", count_today, MAX_POSTS_PER_DAY)

    if remaining <= 0:
        logging.info("Дневной лимит достигнут; публикации не будет.")
        save_json_atomic(STATE_FILE, {
            "last_run_utc": datetime.now(timezone.utc).isoformat(),
            "last_published": 0,
            "total_seen_keys": len(posted_keys),
            "daily_count_after_run": count_today,
            "version": VERSION,
        })
        return

    all_items = []
    feed_successes = 0
    for source, url, kind in RSS_FEEDS:
        fetched = fetch(source, url, kind)
        if fetched:
            feed_successes += 1
        all_items.extend(fetched)

    logging.info("Всего собрано: %d материалов; источников с результатами: %d/%d",
                 len(all_items), feed_successes, len(RSS_FEEDS))

    candidates = select_items(all_items, records)
    logging.info("Кандидатов после фильтрации: %d", len(candidates))

    published = 0
    new_records = []
    for item in candidates[:min(MAX_POSTS_PER_RUN, remaining)]:
        try:
            publish_item(item)
            published_at = int(time.time())
            record = {
                "key": item["_key"],
                "published_at": published_at,
                "title": item["title"][:400],
                "link": item["link"][:1000],
            }
            records.append(record)
            new_records.append(record)
            posted_keys.add(item["_key"])
            published += 1
            time.sleep(2)
        except Exception:
            logging.exception("Не удалось опубликовать материал: %s", item.get("title", ""))

    save_json_atomic(POSTED_FILE, records[-MAX_HISTORY:])
    state = {
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
        "last_published": published,
        "total_seen_keys": len(posted_keys),
        "daily_count_after_run": count_today + published,
        "feeds_with_results": feed_successes,
        "feeds_total": len(RSS_FEEDS),
        "items_collected": len(all_items),
        "candidates": len(candidates),
        "version": VERSION,
    }
    save_json_atomic(STATE_FILE, state)
    logging.info("Опубликовано за запуск: %d", published)


if __name__ == "__main__":
    main()
