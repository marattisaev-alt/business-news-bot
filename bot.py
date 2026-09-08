# -*- coding: utf-8 -*-
import os
import re
import json
import time
import html
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

VERSION = "8.0"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL = os.getenv("CHANNEL", "").strip()

MAX_POSTS_PER_RUN = 2
MAX_NEWS_AGE_HOURS = 48
POSTED_FILE = "posted.json"
STATE_FILE = "state.json"
CARD_FILE = "mrk_card.jpg"
TIMEOUT = 25

RSS_FEEDS = [
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u0411\u0438\u0437\u043d\u0435\u0441", "https://www.vedomosti.ru/rss/rubric/business"),
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u042d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0430", "https://www.vedomosti.ru/rss/rubric/economics"),
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u0424\u0438\u043d\u0430\u043d\u0441\u044b", "https://www.vedomosti.ru/rss/rubric/finance"),
    ("\u0412\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u0438 \u2014 \u0422\u0435\u0445\u043d\u043e\u043b\u043e\u0433\u0438\u0438", "https://www.vedomosti.ru/rss/rubric/technology"),
    ("\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u2014 \u043d\u043e\u0432\u043e\u0441\u0442\u0438", "https://www.cbr.ru/rss/RssNews"),
    ("\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u2014 \u0441\u043e\u0431\u044b\u0442\u0438\u044f", "https://www.cbr.ru/rss/eventrss"),
    ("\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u2014 \u043f\u0440\u0435\u0441\u0441-\u0440\u0435\u043b\u0438\u0437\u044b", "https://www.cbr.ru/rss/RssPress"),
]

LOW_VALUE = [
    "\u0433\u043e\u0440\u043e\u0441\u043a\u043e\u043f", "\u0430\u0441\u0442\u0440\u043e\u043b\u043e\u0433", "\u043f\u043e\u0433\u043e\u0434",
    "\u043a\u043e\u043d\u0446\u0435\u0440\u0442", "\u043a\u0438\u043d\u043e", "\u0441\u0435\u0440\u0438\u0430\u043b"
]

CATEGORY_RULES = {
    "\U0001f4b0 \u0411\u0418\u0417\u041d\u0415\u0421": ["\u043a\u043e\u043c\u043f\u0430\u043d", "\u0431\u0438\u0437\u043d\u0435\u0441", "\u043f\u0440\u043e\u0434\u0430\u0436", "\u0438\u043d\u0432\u0435\u0441\u0442", "\u0441\u0434\u0435\u043b\u043a", "\u043f\u0440\u0438\u0431\u044b\u043b", "\u0432\u044b\u0440\u0443\u0447\u043a"],
    "\U0001f4c8 \u042d\u041a\u041e\u041d\u041e\u041c\u0418\u041a\u0410": ["\u0446\u0431", "\u0441\u0442\u0430\u0432\u043a", "\u0438\u043d\u0444\u043b\u044f\u0446", "\u0440\u0443\u0431\u043b", "\u043d\u0430\u043b\u043e\u0433", "\u044d\u043a\u043e\u043d\u043e\u043c", "\u0431\u044e\u0434\u0436\u0435\u0442"],
    "\U0001f916 \u0422\u0415\u0425\u041d\u041e\u041b\u041e\u0413\u0418\u0418": ["\u0438\u0438", "\u0438\u0441\u043a\u0443\u0441\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439 \u0438\u043d\u0442\u0435\u043b\u043b\u0435\u043a\u0442", "ai", "it", "\u0442\u0435\u0445\u043d\u043e\u043b\u043e\u0433", "\u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c"],
    "\U0001f6d2 \u0420\u042b\u041d\u041e\u041a": ["\u043c\u0430\u0440\u043a\u0435\u0442\u043f\u043b\u0435\u0439\u0441", "ozon", "wildberries", "\u0440\u0438\u0442\u0435\u0439\u043b", "\u043c\u0430\u0433\u0430\u0437\u0438\u043d", "\u043b\u043e\u0433\u0438\u0441\u0442\u0438\u043a"]
}

IMPORTANT_WORDS = [
    "\u0446\u0431", "\u0441\u0442\u0430\u0432\u043a", "\u043d\u0430\u043b\u043e\u0433", "\u0438\u043d\u0444\u043b\u044f\u0446", "\u043a\u0440\u0438\u0437\u0438\u0441",
    "\u0441\u0430\u043d\u043a\u0446", "\u0437\u0430\u043f\u0440\u0435\u0442", "\u0430\u043a\u0442\u0438\u0432", "\u0441\u043b\u0438\u044f\u043d", "\u043f\u043e\u0433\u043b\u043e\u0449",
    "\u043c\u0438\u043b\u043b\u0438\u0430\u0440\u0434", "\u043c\u043b\u043d", "\u043c\u043b\u043b\u0438\u0430\u0440\u0434", "\u0438\u043d\u0432\u0435\u0441\u0442\u0438\u0446"
]

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def repair(s):
    s = clean(s)
    for _ in range(2):
        if not any(x in s for x in ("\u0420\u0458", "\u0420\u0451", "\u0432\u0402", "\u0440\u045f", "\u00d0", "\u00d1")):
            break
        for enc in ("latin1", "cp1252"):
            try:
                fixed = s.encode(enc).decode("utf-8")
                if fixed != s:
                    s = fixed
                    break
            except Exception:
                pass
    return s

def parse_date(s):
    s = clean(s)
    if not s:
        return 0
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp())
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return int(d.timestamp())
        except Exception:
            pass
    return 0

def tag(block, name):
    m = re.search(r"<" + re.escape(name) + r"\b[^>]*>(.*?)</" + re.escape(name) + r">",
                  block, re.I | re.S)
    return repair(m.group(1)) if m else ""

def get_link(block):
    m = re.search(r"<link\b[^>]*>(.*?)</link>", block, re.I | re.S)
    if m:
        return repair(m.group(1))
    m = re.search(r"<link\b[^>]*href=[\"']([^\"']+)[\"']", block, re.I | re.S)
    if m:
        return html.unescape(m.group(1))
    m = re.search(r"<guid\b[^>]*>(https?://.*?)</guid>", block, re.I | re.S)
    return repair(m.group(1)) if m else ""

def parse_feed(data, source):
    text = data.decode("utf-8", errors="replace").replace("\x00", " ")
    blocks = re.findall(r"<item\b[^>]*>(.*?)</item>", text, re.I | re.S)
    if not blocks:
        blocks = re.findall(r"<entry\b[^>]*>(.*?)</entry>", text, re.I | re.S)
    out = []
    for b in blocks:
        title = tag(b, "title")
        link = get_link(b)
        desc = tag(b, "description") or tag(b, "summary") or tag(b, "content")
        pub = tag(b, "pubDate") or tag(b, "published") or tag(b, "updated")
        if title and link:
            out.append({"title": title[:500], "description": desc[:1800],
                        "link": link, "source": source, "published": parse_date(pub)})
    return out

def fetch(source, url):
    print("[RSS]", source)
    try:
        r = requests.get(url, timeout=TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0 MRKNewsBot/8.0", "Accept": "*/*"})
        print("HTTP", r.status_code)
        r.raise_for_status()
        items = parse_feed(r.content, source)
        print("parsed:", len(items))
        return items
    except Exception as e:
        print("feed error:", e)
        return []

def load_posted():
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, list):
            return set(map(str, d))
        if isinstance(d, dict):
            return set(map(str, d.keys()))
    except Exception:
        pass
    return set()

def save_posted(posted):
    tmp = POSTED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(posted)[-3000:], f, ensure_ascii=False, indent=2)
    os.replace(tmp, POSTED_FILE)

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)

def key(a):
    return hashlib.sha256(a["link"].strip().lower().encode("utf-8")).hexdigest()

def fresh(a):
    ts = a.get("published", 0)
    if not ts:
        return True
    age = (time.time() - ts) / 3600
    return -2 <= age <= MAX_NEWS_AGE_HOURS

def classify(a):
    text = (a["title"] + " " + a.get("description", "")).lower()
    best = "\U0001f4b0 \u0411\u0418\u0417\u041d\u0415\u0421"
    best_score = 0
    for category, words in CATEGORY_RULES.items():
        score = sum(1 for w in words if w in text)
        if score > best_score:
            best, best_score = category, score
    return best

def importance(a):
    text = (a["title"] + " " + a.get("description", "")).lower()
    hits = sum(1 for w in IMPORTANT_WORDS if w in text)
    if hits >= 3:
        return 3
    if hits >= 1:
        return 2
    return 1

def why_important(a, category):
    text = (a["title"] + " " + a.get("description", "")).lower()
    if any(w in text for w in ("\u0441\u0442\u0430\u0432\u043a", "\u0446\u0431", "\u0438\u043d\u0444\u043b\u044f\u0446", "\u0430\u043a\u0446\u0438\u0437")):
        return "\u041d\u043e\u0432\u043e\u0441\u0442\u044c \u043c\u043e\u0436\u0435\u0442 \u043f\u043e\u0432\u043b\u0438\u044f\u0442\u044c \u043d\u0430 \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u0434\u0435\u043d\u0435\u0433, \u0437\u0430\u0439\u043c\u043e\u0432 \u0438 \u0440\u0435\u0448\u0435\u043d\u0438\u044f \u0431\u0438\u0437\u043d\u0435\u0441\u0430."
    if any(w in text for w in ("\u0438\u043d\u0432\u0435\u0441\u0442\u0438\u0446", "\u0441\u0434\u0435\u043b\u043a", "\u0441\u043b\u0438\u044f\u043d", "\u043f\u043e\u0433\u043b\u043e\u0449")):
        return "\u041d\u0430 \u0440\u044b\u043d\u043a\u0435 \u043c\u043e\u0436\u0435\u0442 \u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c\u0441\u044f \u0440\u0430\u0441\u043a\u043b\u0430\u0434 \u0441\u0438\u043b \u0438 \u0443\u0441\u043b\u043e\u0432\u0438\u044f \u0434\u043b\u044f \u043a\u043e\u043c\u043f\u0430\u043d\u0438\u0439."
    if category == "\U0001f916 \u0422\u0415\u0425\u041d\u041e\u041b\u041e\u0413\u0418\u0418":
        return "\u0422\u0435\u0445\u043d\u043e\u043b\u043e\u0433\u0438\u044f \u043c\u043e\u0436\u0435\u0442 \u043f\u043e\u0432\u043b\u0438\u044f\u0442\u044c \u043d\u0430 \u0440\u0430\u0441\u0445\u043e\u0434\u044b, \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u0438 \u043a\u043e\u043d\u043a\u0443\u0440\u0435\u043d\u0442\u043d\u044b\u0435 \u043f\u043e\u0437\u0438\u0446\u0438\u0438."
    return "\u0421\u043e\u0431\u044b\u0442\u0438\u0435 \u0438\u043c\u0435\u0435\u0442 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u0434\u043b\u044f \u0440\u044b\u043d\u043a\u0430 \u0438 \u0431\u0438\u0437\u043d\u0435\u0441\u0430."

def select(articles, posted):
    result = []
    for a in articles:
        a["title"], a["description"], a["link"] = repair(a["title"]), repair(a["description"]), repair(a["link"])
        if len(a["title"]) < 10 or not a["link"].startswith(("http://", "https://")):
            continue
        if not fresh(a) or key(a) in posted:
            continue
        if any(x in a["title"].lower() for x in LOW_VALUE):
            continue
        a["_key"] = key(a)
        a["category"] = classify(a)
        a["importance"] = importance(a)
        a["why"] = why_important(a, a["category"])
        result.append(a)
    result.sort(key=lambda x: (x["importance"], x.get("published", 0)), reverse=True)
    return result

def tg(method, data=None, files=None):
    r = requests.post("https://api.telegram.org/bot" + BOT_TOKEN + "/" + method,
                      data=data or {}, files=files, timeout=TIMEOUT)
    try:
        p = r.json()
    except Exception:
        raise RuntimeError(r.text[:300])
    if not p.get("ok"):
        raise RuntimeError(p.get("description", "Telegram API error"))
    return p

def fonts():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    bold = next((x for x in candidates if "Bold" in x and os.path.exists(x)), None)
    regular = next((x for x in candidates if os.path.exists(x)), None)
    return bold, regular

def make_card(a):
    if Image is None:
        return None
    W, H = 1200, 675
    img = Image.new("RGB", (W, H), (18, 20, 28))
    d = ImageDraw.Draw(img)

    # Dynamic abstract background.
    for i in range(0, W, 20):
        shade = int(25 + 35 * i / W)
        d.rectangle((i, 0, i + 20, H), fill=(shade, 28 + shade // 3, 45 + shade // 2))
    d.ellipse((790, -180, 1320, 350), fill=(75, 35, 110))
    d.ellipse((-220, 500, 430, 1050), fill=(25, 70, 120))

    bold_path, regular_path = fonts()
    if not bold_path:
        return None
    fb = ImageFont.truetype(bold_path, 52)
    fs = ImageFont.truetype(regular_path or bold_path, 28)
    small = ImageFont.truetype(regular_path or bold_path, 24)

    d.text((55, 45), "MRK", font=fb, fill=(255, 255, 255))
    d.text((55, 112), a["category"], font=small, fill=(225, 225, 235))

    label = "\u0421\u0420\u041e\u0427\u041d\u041e" if a["importance"] == 3 else "\u0413\u041b\u0410\u0412\u041d\u041e\u0415" if a["importance"] == 2 else "\u041d\u041e\u0412\u041e\u0421\u0422\u042c"
    d.rounded_rectangle((900, 42, 1145, 100), radius=18, fill=(255, 255, 255))
    d.text((925, 55), label, font=small, fill=(25, 25, 30))

    title = a["title"]
    words = title.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if d.textbbox((0, 0), test, font=fb)[2] <= 1080:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    lines = lines[:4]
    y = 205
    for line in lines:
        d.text((55, y), line, font=fb, fill=(255, 255, 255))
        y += 65

    d.line((55, 510, 1145, 510), fill=(150, 150, 160), width=2)
    d.text((55, 535), a["source"], font=small, fill=(220, 220, 230))
    d.text((55, 585), "MRK | \u0411\u0418\u0417\u041d\u0415\u0421 \u041d\u041e\u0412\u041e\u0421\u0422\u0418", font=small, fill=(220, 220, 230))

    img.save(CARD_FILE, quality=92, optimize=True)
    return CARD_FILE

def build_post(a):
    icon = "\U0001f680" if a["importance"] == 3 else "\U0001f525" if a["importance"] == 2 else "\U0001f4f0"
    title = html.escape(a["title"])
    why = html.escape(a["why"])
    source = html.escape(a["source"])
    link = html.escape(a["link"], quote=True)
    return (
        f"{icon} <b>{title}</b>\n\n"
        f"<b>{html.escape(a['category'])}</b>\n\n"
        f"\U0001f4a1 <b>\u041f\u043e\u0447\u0435\u043c\u0443 \u044d\u0442\u043e \u0432\u0430\u0436\u043d\u043e?</b>\n"
        f"{why}\n\n"
        f"\U0001f4cc <b>{source}</b>\n"
        f"\U0001f517 <a href=\"{link}\">\u0427\u0438\u0442\u0430\u0442\u044c \u043f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435</a>"
    )

def send_article(a):
    card = make_card(a)
    if card and os.path.exists(card):
        caption = build_post(a)
        try:
            with open(card, "rb") as f:
                tg("sendPhoto", {"chat_id": CHANNEL, "caption": caption, "parse_mode": "HTML"}, {"photo": f})
            return
        except Exception as e:
            print("[CARD] fallback:", e)
    tg("sendMessage", {"chat_id": CHANNEL, "text": build_post(a), "parse_mode": "HTML"})

def main():
    print("MRK BUSINESS NEWS - VERSION " + VERSION)
    print("=" * 60)
    if not BOT_TOKEN or not CHANNEL:
        raise RuntimeError("BOT_TOKEN or CHANNEL is empty")

    me = tg("getMe", {})["result"]["username"]
    print("Bot connected:", me)

    posted = load_posted()
    state = load_state()
    print("posted history:", len(posted))

    all_items = []
    for source, url in RSS_FEEDS:
        all_items.extend(fetch(source, url))

    print("total collected:", len(all_items))
    candidates = select(all_items, posted)
    print("new candidates:", len(candidates))

    selected = candidates[:MAX_POSTS_PER_RUN]
    print("to publish:", len(selected))

    published = 0
    for a in selected:
        print("[POST]", a["title"])
        try:
            send_article(a)
            posted.add(a["_key"])
            published += 1
            print("[OK] Published")
            time.sleep(2)
        except Exception as e:
            print("[ERROR]", e)

    # Save a compact state for future daily rubrics.
    now = datetime.now(timezone.utc).isoformat()
    state["last_run_utc"] = now
    state["last_published"] = published
    save_state(state)
    save_posted(posted)

    print("published this run:", published)
    print("posted history now:", len(posted))

if __name__ == "__main__":
    main()
