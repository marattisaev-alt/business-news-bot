# -*- coding: utf-8 -*-
"""
MRK | БЕЗ ФИЛЬТРОВ — autonomous entertainment Telegram bot.
Collects RSS items, deduplicates, scores, and publishes concise posts.
Only use feeds you are permitted to access and media you have right
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

VERSION = "9.0"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL = os.getenv("CHANNEL", "").strip()

MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "2"))
MAX_ITEM_AGE_HOURS = int(os.getenv("MAX_ITEM_AGE_HOURS", "36"))
POSTED_FILE = "posted.json"
STATE_FILE = "state.json"
TIMEOUT = 25
MAX_HISTORY = 5000

# Replace or extend these with working, permitted RSS feeds relevant to your audience.
# RSS is preferred over scraping social media. A feed can stop working or change format.
RSS_FEEDS = [
    ("Meduza — Популярное", "https://meduza.io/rss/all"),
    ("РИА Новости — Культура", "https://ria.ru/export/rss2/archive/index.xml"),
]

# These topics are scored for entertainment relevance, not factual importance.
CATEGORY_RULES = {
    "😂 ЮМОР И МЕМЫ": [
        "мем", "смешн", "юмор", "шутк", "прикол", "комикс", "сарказм",
        "жиза", "забавно", "анекдот"
    ],
    "🔥 ВИРУСНОЕ": [
        "вирусн", "завирус", "обсуждают", "разлетел", "соцсет", "интернет",
        "ролик", "видео", "тренд", "флешмоб"
    ],
    "👀 БЛОГЕРЫ И ЗВЁЗДЫ": [
        "блогер", "инфлюенсер", "стример", "ютуб", "youtube", "тикток",
        "tiktok", "телеграм-канал", "артист", "актёр", "певиц", "звезд"
    ],
    "🤯 НЕОБЫЧНЫЕ ИСТОРИИ": [
        "необыч", "странн", "курьез", "курьёз", "удивитель", "неожидан",
        "случай", "история", "рекорд", "животн"
    ],
}
BLOCK_TERMS = [
    "казино", "ставки на спорт", "эротика", "порно", "шок-контент",
    "жестокое обращение", "суицид", "теракт"
]
HEADERS = {"User-Agent": "Mozilla/5.0 MRKEntertainmentBot/9.0", "Accept": "*/*"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def clean(value):
    value = html.unescape(value or "")
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


def parse_feed(content, source):
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logging.warning("Cannot parse feed %s: %s", source, exc)
        return []
    items = []
    for node in root.iter():
        if local_name(node.tag) not in ("item", "entry"):
            continue
        fields = {}
        for child in list(node):
            name = local_name(child.tag)
            text = "".join(child.itertext()).strip()
            if name not in fields and text:
                fields[name] = text
            if name == "link" and child.attrib.get("href"):
                fields["link"] = child.attrib["href"]
        title = clean(fields.get("title", ""))
        link = clean(fields.get("link", fields.get("guid", "")))
        description = clean(fields.get("description", fields.get("summary", fields.get("content", ""))))
        pub = fields.get("pubdate", fields.get("published", fields.get("updated", fields.get("date", ""))))
        if title and link.startswith(("https://", "http://")):
            items.append({
                "title": title[:400],
                "description": description[:1200],
                "link": link,
                "source": source,
                "published": parse_date(pub),
            })
    return items


def fetch(source, url):
    logging.info("Fetching %s", source)
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        items = parse_feed(response.content, source)
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


def load_posted():
    data = load_json(POSTED_FILE, [])
    if isinstance(data, dict):
        return set(map(str, data.keys()))
    if isinstance(data, list):
        return set(map(str, data))
    return set()


def save_posted(posted):
    save_json_atomic(POSTED_FILE, list(posted)[-MAX_HISTORY:])


def item_key(item):
    # Link hash plus normalized title catches the same story reposted through another URL.
    normalized_title = re.sub(r"\W+", " ", item["title"].lower()).strip()
    raw = item["link"].strip().lower() + "|" + normalized_title
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_fresh(item):
    timestamp = item.get("published", 0)
    if not timestamp:
        return True
    age_hours = (time.time() - timestamp) / 3600
    return -2 <= age_hours <= MAX_ITEM_AGE_HOURS


def classify(item):
    text = (item["title"] + " " + item.get("description", "")).lower()
    scores = {
        category: sum(1 for term in terms if term in text)
        for category, terms in CATEGORY_RULES.items()
    }
    category, score = max(scores.items(), key=lambda pair: pair[1])
    return category if score else "🔥 ВИРУСНОЕ", score


def score_item(item):
    text = (item["title"] + " " + item.get("description", "")).lower()
    category, hits = classify(item)
    score = hits * 3
    # Prefer concrete, readable headlines and items with a description.
    if 25 <= len(item["title"]) <= 140:
        score += 1
    if item.get("description"):
        score += 1
    if any(term in text for term in BLOCK_TERMS):
        return -100, category
    if len(item["title"]) < 12:
        score -= 3
    return score, category


def select_items(items, posted):
    selected = []
    seen_keys = set()
    seen_titles = set()
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
        if key in posted or key in seen_keys or normalized_title in seen_titles:
            continue
        score, category = score_item(item)
        if score < 1:
            continue
        item["_key"] = key
        item["_score"] = score
        item["category"] = category
        seen_keys.add(key)
        seen_titles.add(normalized_title)
        selected.append(item)
    selected.sort(key=lambda item: (item["_score"], item.get("published", 0)), reverse=True)
    return selected


def telegram(method, data=None):
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data or {},
        timeout=TIMEOUT,
    )
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
    description = item.get("description", "")
    # Use the source's description only when it adds context; don't invent facts.
    description = html.escape(description[:500])
    parts = [f"🔥 <b>{title}</b>"]
    if description and description.lower() not in title.lower():
        parts.extend(["", description])
    parts.extend(["", f"{category}", "", f"📰 <a href=\"{link}\">Источник: {source}</a>", "", "#МРКБезФильтров"])
    return "\n".join(parts)[:1024]


def publish(item):
    telegram("sendMessage", {
        "chat_id": CHANNEL,
        "text": build_post(item),
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })


def main():
    logging.info("MRK | БЕЗ ФИЛЬТРОВ — version %s", VERSION)
    if not BOT_TOKEN or not CHANNEL:
        raise RuntimeError("BOT_TOKEN or CHANNEL is empty. Set GitHub Secrets BOT_TOKEN and CHANNEL.")

    bot = telegram("getMe")["result"]
    logging.info("Connected bot: @%s", bot.get("username", "unknown"))

    posted = load_posted()
    all_items = []
    for source, url in RSS_FEEDS:
        all_items.extend(fetch(source, url))

    logging.info("Collected %d items", len(all_items))
    candidates = select_items(all_items, posted)
    logging.info("Candidates after filtering: %d", len(candidates))

    published = 0
    for item in candidates[:max(0, MAX_POSTS_PER_RUN)]:
        logging.info("Publishing: %s", item["title"])
        try:
            publish(item)
            posted.add(item["_key"])
            published += 1
            time.sleep(2)
        except Exception:
            logging.exception("Publish failed")
    save_posted(posted)
    state = load_json(STATE_FILE, {})
    state["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    state["last_published"] = published
    state["total_seen_keys"] = len(posted)
    save_json_atomic(STATE_FILE, state)
    logging.info("Published %d post(s)", published)


if __name__ == "__main__":
    main()
