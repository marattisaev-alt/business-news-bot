# -*- coding: utf-8 -*-
"""МРК | БЕЗ ФИЛЬТРОВ — entertainment RSS bot.
Collects Russian-language entertainment stories, filters business/politics,
deduplicates across runs, and publishes at most six posts per UTC day.
Only use source text/media in accordance with each publisher's terms.
"""
import os
import re
import json
import time
import html
import hashlib
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

VERSION = "10.0"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL = os.getenv("CHANNEL", "").strip()
MAX_POSTS_PER_DAY = max(1, int(os.getenv("MAX_POSTS_PER_DAY", "6")))
MAX_POSTS_PER_RUN = max(1, int(os.getenv("MAX_POSTS_PER_RUN", "1")))
MAX_ITEM_AGE_HOURS = max(1, int(os.getenv("MAX_ITEM_AGE_HOURS", "36")))
POSTED_FILE = "posted.json"
STATE_FILE = "state.json"
TIMEOUT = 20
MAX_HISTORY = 5000

# Russian-language entertainment sources. RSS endpoints can change; failed feeds are skipped.
RSS_FEEDS = [
    ("Афиша Daily", "https://daily.afisha.ru/export/rss/google_newsstand/", "culture"),
    ("Onedio — Развлечение", "https://onedio.ru/Publisher/publisher-razvlechenie.rss", "viral"),
    ("Fishki.net", "https://fishki.net/rss/", "humor"),
    ("Pikabu — популярное", "https://pikabu.ru/xmlfeeds.php?cmd=popular", "viral"),
    ("Anekdot.ru — юмор", "https://www.anekdot.ru/rss/export_j_burning.xml", "humor"),
    ("Meduza — интернет и мемы", "https://meduza.io/rss/all", "viral"),
]

CATEGORY_RULES = {
    "😂 ЮМОР И МЕМЫ": ["мем", "смешн", "юмор", "шутк", "прикол", "комикс", "сарказм", "жиза", "забавно", "анекдот", "смех", "котик", "кот", "собак", "смешной"],
    "🔥 ВИРУСНОЕ": ["вирусн", "завирус", "обсуждают", "разлетел", "соцсет", "интернет", "ролик", "видео", "тренд", "флешмоб", "пользовател", "комментарии", "в сети"],
    "👀 БЛОГЕРЫ И ЗВЁЗДЫ": ["блогер", "инфлюенсер", "стример", "ютуб", "youtube", "тикток", "tiktok", "телеграм-канал", "артист", "актёр", "актер", "певиц", "звезд", "шоу", "селебрити"],
    "🤯 НЕОБЫЧНЫЕ ИСТОРИИ": ["необыч", "странн", "курьез", "курьёз", "удивитель", "неожидан", "случай", "история", "рекорд", "животн", "уморитель", "невероят"],
    "🎬 КУЛЬТУРА И ПОП-КУЛЬТУРА": ["кино", "фильм", "сериал", "музык", "премьера", "альбом", "актёр", "актер", "певец", "певица", "шоу", "концерт", "мультфильм"],
}

# If these appear in title/description, reject the item even if the feed is broad.
BLOCK_TERMS = [
    "бизнес", "экономик", "бирж", "акци", "инвестици", "кредит", "налог", "банк россии",
    "ставка цб", "политик", "выборы", "государственная дума", "военн", "обстрел", "теракт",
    "погиб", "погибли", "убийств", "насили", "казино", "ставки на спорт", "эротика", "порно",
    "шок-контент", "жестокое обращение", "суицид", "оружие", "взрыв"
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MRKEntertainmentBot/10.0; +https://github.com/marattisaev-alt/business-news-bot)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"}
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
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return 0


def local_name(tag):
    return tag.rsplit("}", 1)[-1].lower()


def parse_feed(content, source, feed_kind):
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logging.warning("Cannot parse feed %s: %s", source, exc)
        return []
    items = []
    for node in root.iter():
        if local_name(node.tag) not in ("item", "entry"):
            continue
        fields, image_url = {}, ""
        for child in list(node):
            name = local_name(child.tag)
            text = "".join(child.itertext()).strip()
            if name not in fields and text:
                fields[name] = text
            if name == "link":
                href = child.attrib.get("href", "")
                if href:
                    fields["link"] = href
            # Recognize standard RSS media fields, but don't repost images automatically.
            if name in ("thumbnail", "content") and child.attrib.get("url"):
                media_type = child.attrib.get("type", "")
                candidate = child.attrib["url"]
                if candidate.startswith("https://") and (not media_type or media_type.startswith("image/")):
                    image_url = candidate
        title = clean(fields.get("title", ""))
        link = clean(fields.get("link", fields.get("guid", "")))
        description = clean(fields.get("description", fields.get("summary", fields.get("encoded", fields.get("content", "")))))
        pub = fields.get("pubdate", fields.get("published", fields.get("updated", fields.get("date", ""))))
        if title and link.startswith(("https://", "http://")):
            items.append({"title": title[:400], "description": description[:1600], "link": link,
                          "source": source, "feed_kind": feed_kind, "published": parse_date(pub),
                          "image_url": image_url})
    return items


def fetch(source, url, feed_kind):
    logging.info("Fetching %s", source)
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        items = parse_feed(response.content, source, feed_kind)
        logging.info("%s: parsed %d items", source, len(items))
        return items
    except Exception as exc:
        logging.warning("Feed error (%s): %s", source, exc)
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
                records.append({"key": str(entry["key"]), "published_at": int(entry.get("published_at", 0) or 0)})
            elif isinstance(entry, str):
                # Backward compatibility with older posted.json containing only hashes.
                records.append({"key": entry, "published_at": 0})
    elif isinstance(raw, dict):
        for key, value in raw.items():
            records.append({"key": str(key), "published_at": int(value or 0) if str(value or "0").isdigit() else 0})
    return records[-MAX_HISTORY:]


def item_key(item):
    normalized_title = re.sub(r"\W+", " ", item["title"].lower()).strip()
    raw = item["link"].strip().lower().split("?")[0] + "|" + normalized_title
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_fresh(item):
    timestamp = item.get("published", 0)
    if not timestamp:
        return True
    age_hours = (time.time() - timestamp) / 3600
    return -2 <= age_hours <= MAX_ITEM_AGE_HOURS


def classify(item):
    text = (item["title"] + " " + item.get("description", "")).lower()
    scores = {category: sum(1 for term in terms if term in text) for category, terms in CATEGORY_RULES.items()}
    category, score = max(scores.items(), key=lambda pair: pair[1])
    if score:
        return category, score
    kind = item.get("feed_kind")
    if kind == "humor":
        return "😂 ЮМОР И МЕМЫ", 1
    if kind == "culture":
        return "🎬 КУЛЬТУРА И ПОП-КУЛЬТУРА", 1
    return "🔥 ВИРУСНОЕ", 1


def score_item(item):
    text = (item["title"] + " " + item.get("description", "")).lower()
    if any(term in text for term in BLOCK_TERMS):
        return -100, ""
    category, hits = classify(item)
    # Broad feeds only pass if the headline contains entertainment/viral signals.
    explicit_signals = any(term in text for terms in CATEGORY_RULES.values() for term in terms)
    if item.get("feed_kind") == "viral" and not explicit_signals:
        return -2, category
    score = hits * 3
    if 22 <= len(item["title"]) <= 140:
        score += 1
    if item.get("description"):
        score += 1
    if len(item["title"]) < 12:
        score -= 3
    return score, category


def select_items(items, posted_keys):
    selected, seen_keys, seen_titles = [], set(), set()
    for item in items:
        item["title"] = clean(item.get("title", ""))
        item["description"] = clean(item.get("description", ""))
        item["link"] = clean(item.get("link", ""))
        if len(item["title"]) < 12 or not item["link"].startswith(("https://", "http://")):
            continue
        if not is_fresh(item):
            continue
        key = item_key(item)
        normalized_title = re.sub(r"\W+", " ", item["title"].lower()).strip()
        if key in posted_keys or key in seen_keys or normalized_title in seen_titles:
            continue
        score, category = score_item(item)
        if score < 1:
            continue
        item["_key"], item["_score"], item["category"] = key, score, category
        seen_keys.add(key)
        seen_titles.add(normalized_title)
        selected.append(item)
    selected.sort(key=lambda item: (item["_score"], item.get("published", 0)), reverse=True)
    return selected


def telegram(method, data=None):
    response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", data=data or {}, timeout=TIMEOUT)
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(response.text[:300])
    if not response.ok or not result.get("ok"):
        raise RuntimeError(result.get("description", f"Telegram HTTP {response.status_code}"))
    return result


def build_post(item):
    title = html.escape(item["title"])
    category = html.escape(item["category"])
    source = html.escape(item["source"])
    link = html.escape(item["link"], quote=True)
    description = clean(item.get("description", ""))
    # Keep excerpts short and never invent details not present in the source.
    if description and description.lower() not in item["title"].lower():
        description = html.escape(description[:320])
    parts = [f"🔥 <b>{title}</b>"]
    if description:
        parts.extend(["", description])
    parts.extend(["", category, "", f'📰 <a href="{link}">Источник: {source}</a>', "", "#МРКБезФильтров"])
    message = "\n".join(parts)
    return message[:1000]


def daily_count(records, now_ts):
    today = datetime.fromtimestamp(now_ts, timezone.utc).date()
    return sum(1 for r in records if r.get("published_at", 0) and datetime.fromtimestamp(r["published_at"], timezone.utc).date() == today)


def main():
    logging.info("MRK | БЕЗ ФИЛЬТРОВ — version %s", VERSION)
    if not BOT_TOKEN or not CHANNEL:
        raise RuntimeError("BOT_TOKEN or CHANNEL is empty. Set GitHub Secrets BOT_TOKEN and CHANNEL.")
    bot = telegram("getMe")["result"]
    logging.info("Connected bot: @%s", bot.get("username", "unknown"))

    records = load_posted_records()
    posted_keys = {record["key"] for record in records}
    now_ts = int(time.time())
    count_today = daily_count(records, now_ts)
    remaining = MAX_POSTS_PER_DAY - count_today
    logging.info("Already published today: %d; daily limit: %d", count_today, MAX_POSTS_PER_DAY)
    if remaining <= 0:
        logging.info("Daily limit reached; exiting without publishing")
        return

    all_items = []
    for source, url, kind in RSS_FEEDS:
        all_items.extend(fetch(source, url, kind))
    logging.info("Collected %d items", len(all_items))
    candidates = select_items(all_items, posted_keys)
    logging.info("Candidates after filtering: %d", len(candidates))

    published = 0
    for item in candidates[:min(MAX_POSTS_PER_RUN, remaining)]:
        logging.info("Publishing: %s", item["title"])
        try:
            publish_result = telegram("sendMessage", {
                "chat_id": CHANNEL,
                "text": build_post(item),
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            })
            records.append({"key": item["_key"], "published_at": int(time.time())})
            posted_keys.add(item["_key"])
            published += 1
            time.sleep(2)
        except Exception:
            logging.exception("Publish failed")
    save_json_atomic(POSTED_FILE, records[-MAX_HISTORY:])
    state = load_json(STATE_FILE, {})
    state["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    state["last_published"] = published
    state["total_seen_keys"] = len(posted_keys)
    state["daily_count_after_run"] = count_today + published
    save_json_atomic(STATE_FILE, state)
    logging.info("Published %d post(s)", published)


if __name__ == "__main__":
    main()
