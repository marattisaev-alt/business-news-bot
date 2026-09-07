import os
import re
import json
import time
import html
import hashlib
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

VERSION = "7.3"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL = os.getenv("CHANNEL", "").strip()

MAX_POSTS_PER_RUN = 2
MAX_NEWS_AGE_HOURS = 48
POSTED_FILE = "posted.json"
TIMEOUT = 25

# These are current public feeds confirmed from the publishers.
RSS_FEEDS = [
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u0411\u0438\u0437\u043d\u0435\u0441", "https://www.vedomosti.ru/rss/rubric/business"),
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u042d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0430", "https://www.vedomosti.ru/rss/rubric/economics"),
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u0424\u0438\u043d\u0430\u043d\u0441\u044b", "https://www.vedomosti.ru/rss/rubric/finance"),
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u0422\u0435\u0445\u043d\u043e\u043b\u043e\u0433\u0438\u0438", "https://www.vedomosti.ru/rss/rubric/technology"),
    ("\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u2014 \u043d\u043e\u0432\u043e\u0441\u0442\u0438", "https://www.cbr.ru/rss/RssNews"),
    ("\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u2014 \u0441\u043e\u0431\u044b\u0442\u0438\u044f", "https://www.cbr.ru/rss/eventrss"),
    ("\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u2014 \u043f\u0440\u0435\u0441\u0441-\u0440\u0435\u043b\u0438\u0437\u044b", "https://www.cbr.ru/rss/RssPress"),
]

# RB.RU currently returns malformed XML from some RSS endpoints.
# We therefore use its public news page as a fallback source.
RB_NEWS_URL = "https://rb.ru/news/"

LOW_VALUE_WORDS = [
    "\u0433\u043e\u0440\u043e\u0441\u043a\u043e\u043f",
    "\u0430\u0441\u0442\u0440\u043e\u043b\u043e\u0433",
    "\u043f\u043e\u0433\u043e\u0434",
    "\u043a\u043e\u043d\u0446\u0435\u0440\u0442",
    "\u043a\u0438\u043d\u043e\u0444\u0438\u043b\u044c\u043c",
    "\u0441\u0435\u0440\u0438\u0430\u043b",
    "\u0437\u043d\u0430\u043a\u043e\u043c\u0441\u0442\u0432",
]

MOJIBAKE = ("\u0420\u0458", "\u0420\u0451", "\u0432\u0402", "\u0440\u045f", "\u00d0", "\u00d1")

def repair(text):
    text = html.unescape(text or "")
    for _ in range(2):
        if not any(x in text for x in MOJIBAKE):
            break
        for enc in ("latin1", "cp1252"):
            try:
                fixed = text.encode(enc).decode("utf-8")
                if fixed != text:
                    text = fixed
                    break
            except Exception:
                pass
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def timestamp(value):
    value = repair(value)
    if not value:
        return 0
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            pass
    return 0

def tag(block, name):
    m = re.search(r"<" + re.escape(name) + r"\b[^>]*>(.*?)</" + re.escape(name) + r">",
                  block, re.I | re.S)
    return repair(m.group(1)) if m else ""

def link_from_block(block):
    m = re.search(r"<link\b[^>]*>(.*?)</link>", block, re.I | re.S)
    if m:
        return repair(m.group(1))
    m = re.search(r"<link\b[^>]*href=[\"']([^\"']+)[\"']", block, re.I | re.S)
    if m:
        return html.unescape(m.group(1))
    m = re.search(r"<guid\b[^>]*>(https?://.*?)</guid>", block, re.I | re.S)
    return repair(m.group(1)) if m else ""

def parse_xml(data, source):
    text = data.decode("utf-8", errors="replace")
    text = text.replace("\x00", " ")
    blocks = re.findall(r"<item\b[^>]*>(.*?)</item>", text, re.I | re.S)
    if not blocks:
        blocks = re.findall(r"<entry\b[^>]*>(.*?)</entry>", text, re.I | re.S)

    out = []
    for block in blocks:
        title = tag(block, "title")
        link = link_from_block(block)
        desc = tag(block, "description") or tag(block, "summary") or tag(block, "content")
        pub = tag(block, "pubDate") or tag(block, "published") or tag(block, "updated")
        if title and link:
            out.append({
                "title": title[:500],
                "description": desc[:1500],
                "link": link,
                "source": source,
                "published": timestamp(pub),
            })
    return out

def fetch_rss(source, url):
    print("[RSS] " + source)
    try:
        r = requests.get(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 MRKNewsBot/7.3", "Accept": "*/*"},
        )
        print("HTTP", r.status_code)
        r.raise_for_status()
        items = parse_xml(r.content, source)
        print("parsed:", len(items))
        return items
    except Exception as exc:
        print("feed error:", exc)
        return []

def fetch_rb():
    source = "RB.RU"
    print("[WEB] RB.RU news")
    try:
        r = requests.get(
            RB_NEWS_URL,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 MRKNewsBot/7.3", "Accept": "text/html,*/*"},
        )
        print("HTTP", r.status_code)
        r.raise_for_status()
        text = r.text

        # Extract article cards from the public news page.
        pattern = re.compile(
            r'<a[^>]+href=["\'](https?://rb\.ru/[^"\']+)["\'][^>]*>(.*?)</a>',
            re.I | re.S
        )
        seen = set()
        items = []

        for m in pattern.finditer(text):
            url = html.unescape(m.group(1))
            title = repair(m.group(2))
            if "/news/" not in url:
                continue
            if len(title) < 20 or len(title) > 350:
                continue
            key = url.split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "title": title,
                "description": "",
                "link": key,
                "source": source,
                "published": 0,
            })

        print("parsed:", len(items))
        return items[:80]
    except Exception as exc:
        print("RB web error:", exc)
        return []

def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(map(str, data))
        if isinstance(data, dict):
            return set(map(str, data.keys()))
    except Exception as exc:
        print("posted.json error:", exc)
    return set()

def save_posted(posted):
    tmp = POSTED_FILE + ".tmp"
    values = list(posted)[-3000:]
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)
    os.replace(tmp, POSTED_FILE)

def key(article):
    value = article["link"] or article["title"]
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

def fresh(article):
    ts = article.get("published", 0)
    if not ts:
        return True
    age = (time.time() - ts) / 3600
    return -2 <= age <= MAX_NEWS_AGE_HOURS

def low_value(title):
    t = title.lower()
    return any(x in t for x in LOW_VALUE_WORDS)

def choose(articles, posted):
    result = []
    for a in articles:
        a["title"] = repair(a.get("title", ""))
        a["description"] = repair(a.get("description", ""))
        a["link"] = repair(a.get("link", ""))
        if len(a["title"]) < 10:
            continue
        if not a["link"].startswith(("http://", "https://")):
            continue
        if not fresh(a):
            continue
        if key(a) in posted:
            continue
        if low_value(a["title"]):
            print("[SKIP] low-value:", a["title"])
            continue
        a["_key"] = key(a)
        result.append(a)

    result.sort(key=lambda x: x.get("published", 0), reverse=True)
    return result

def tg(method, data):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/" + method
    r = requests.post(url, data=data, timeout=TIMEOUT)
    try:
        payload = r.json()
    except Exception:
        raise RuntimeError("Telegram returned non-JSON response: " + r.text[:300])
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "Telegram API error"))
    return payload

def post(article):
    text = (
        "\U0001f4f0 <b>" + html.escape(article["title"]) + "</b>\n\n"
        "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a: " + html.escape(article["source"]) + "\n\n"
        "\U0001f517 <a href=\"" + html.escape(article["link"], quote=True) + "\">\u0427\u0438\u0442\u0430\u0442\u044c \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a</a>"
    )
    tg("sendMessage", {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })

def main():
    print("MRK BUSINESS NEWS - VERSION " + VERSION)
    print("=" * 60)

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")
    if not CHANNEL:
        raise RuntimeError("CHANNEL is empty")

    me = tg("getMe", {})["result"]["username"]
    print("Bot connected:", me)

    posted = load_posted()
    print("posted history:", len(posted))

    all_items = []
    for source, url in RSS_FEEDS:
        all_items.extend(fetch_rss(source, url))
    all_items.extend(fetch_rb())

    print("total collected:", len(all_items))

    candidates = choose(all_items, posted)
    print("new candidates:", len(candidates))

    selected = candidates[:MAX_POSTS_PER_RUN]
    print("to publish:", len(selected))

    if not selected:
        print("Nothing new to publish.")
        return

    published = 0
    for article in selected:
        print("[POST]", article["title"])
        try:
            post(article)
            posted.add(article["_key"])
            published += 1
            print("[OK] Published")
            time.sleep(2)
        except Exception as exc:
            print("[ERROR]", exc)

    save_posted(posted)
    print("published this run:", published)
    print("posted history now:", len(posted))

if __name__ == "__main__":
    main()
