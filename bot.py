import os
import re
import json
import html
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import requests

VERSION = "7.1"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")
MAX_POSTS_PER_RUN = 2
MAX_NEWS_AGE_HOURS = 48
POSTED_FILE = "posted.json"
TIMEOUT = 20
MAX_IMAGE_SIZE = 9 * 1024 * 1024

# Source names are ASCII on purpose. News titles themselves remain untouched.
RSS_FEEDS = [
    ("Vedomosti Business", "https://www.vedomosti.ru/rss/business"),
    ("Vedomosti Economics", "https://www.vedomosti.ru/rss/economics"),
    ("Vedomosti Technology", "https://www.vedomosti.ru/rss/technology"),
    ("Vedomosti Entrepreneurship", "https://www.vedomosti.ru/rss/entrepreneurship"),
    ("Vedomosti Finance", "https://www.vedomosti.ru/rss/finance"),
    ("CBR News", "https://www.cbr.ru/rss/eventrss/"),
    ("CBR Press", "https://www.cbr.ru/rss/RssPress/"),
    ("RB IT", "https://rb.ru/rss/it/"),
    ("RB AI", "https://rb.ru/rss/ai/"),
    ("RB Ecommerce", "https://rb.ru/rss/e-commerce/"),
]

# ASCII keywords. The filter is deliberately permissive because feeds are already business-oriented.
TOPIC_WORDS = {
    "business", "company", "companies", "entrepreneur", "entrepreneurs",
    "investment", "investments", "investor", "investors", "deal", "deals",
    "startup", "startups", "revenue", "profit", "loss", "market", "markets",
    "economy", "economic", "inflation", "deflation", "rate", "budget", "tax",
    "taxes", "credit", "mortgage", "finance", "financial", "bank", "banking",
    "technology", "technologies", "digital", "software", "developer", "developers",
    "ai", "robot", "robots", "cybersecurity", "telecom", "cloud", "data", "processor",
    "oil", "gas", "energy", "metallurgy", "metal", "coal", "mining", "construction",
    "real estate", "automotive", "aviation", "pharma", "medicine", "agriculture",
    "food", "logistics", "export", "import", "retail", "ecommerce", "marketplace",
    "ozon", "wildberries", "sber", "yandex",
}

LOW_VALUE_WORDS = {
    "sport", "football", "hockey", "match", "movie", "music", "show", "horoscope",
    "recipe", "weather", "crime",
}

SOURCE_PRIORITY = {
    "CBR News": 5,
    "CBR Press": 5,
    "Vedomosti Business": 5,
    "Vedomosti Economics": 5,
    "Vedomosti Finance": 5,
    "Vedomosti Technology": 4,
    "Vedomosti Entrepreneurship": 4,
    "RB IT": 4,
    "RB AI": 4,
    "RB Ecommerce": 4,
}


def clean_text(value):
    if value is None:
        return ""
    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize(value):
    value = clean_text(value).lower()
    value = value.replace("С‘", "Рµ")
    return re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)


def parse_date(value):
    if not value:
        return None
    value = clean_text(value)
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def child_text(item, names):
    for name in names:
        node = item.find(name)
        if node is not None and node.text:
            return clean_text(node.text)
    return ""


def parse_rss(data, source):
    articles = []
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        print("[RSS] XML parse error:", source, exc)
        return articles

    atom_link = "{http://www.w3.org/2005/Atom}link"
    atom_title = "{http://www.w3.org/2005/Atom}title"
    atom_summary = "{http://www.w3.org/2005/Atom}summary"
    atom_published = "{http://www.w3.org/2005/Atom}published"
    atom_updated = "{http://www.w3.org/2005/Atom}updated"

    for item in root.iter():
        tag = item.tag.lower() if isinstance(item.tag, str) else ""
        if not tag.endswith("item") and not tag.endswith("entry"):
            continue

        title = child_text(item, ["title", atom_title])
        link = child_text(item, ["link", atom_link])
        if not link:
            link_node = item.find(atom_link)
            if link_node is not None:
                link = clean_text(link_node.attrib.get("href", ""))

        description = child_text(item, ["description", "summary", atom_summary])
        pub = child_text(
            item,
            [
                "pubDate",
                "published",
                "updated",
                atom_published,
                atom_updated,
            ],
        )

        if title and link:
            articles.append(
                {
                    "title": title,
                    "link": link,
                    "description": description,
                    "published": parse_date(pub),
                    "source": source,
                }
            )

    return articles


def fetch_all_feeds():
    all_articles = []
    for source, url in RSS_FEEDS:
        print("\n[RSS]", source)
        try:
            response = requests.get(
                url,
                timeout=TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MRKNewsBot/7.1)"},
            )
            print("HTTP", response.status_code)
            response.raise_for_status()
            articles = parse_rss(response.content, source)
            print("received:", len(articles))
            all_articles.extend(articles)
        except Exception as exc:
            print("feed error:", exc)
    return all_articles


def article_key(article):
    link = clean_text(article.get("link", "")).strip()
    if link:
        return link.split("#", 1)[0].rstrip("/")
    return normalize(article.get("title", ""))


def topic_hits(article):
    # Only used as a soft score. It never blocks a normal feed item.
    text = normalize(article.get("title", "") + " " + article.get("description", ""))
    hits = []
    for word in TOPIC_WORDS:
        if normalize(word) in text:
            hits.append(word)
    return hits


def article_is_relevant(article):
    title = clean_text(article.get("title", ""))
    if len(title) < 10:
        return False

    # Do not reject normal business feeds because of language or inflection.
    # Only reject obvious low-value titles when no business signal is present.
    title_normalized = normalize(title)
    hits = topic_hits(article)
    if any(normalize(word) in title_normalized for word in LOW_VALUE_WORDS) and not hits:
        print("[FILTER] low-value:", title)
        return False
    return True


def is_fresh(article):
    published = article.get("published")
    if not published:
        return True
    age = datetime.now(timezone.utc) - published
    return age <= timedelta(hours=MAX_NEWS_AGE_HOURS)


def deduplicate(articles):
    result = []
    seen = set()
    for article in articles:
        key = article_key(article)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result


def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        print("posted.json read error:", exc)
        return []


def save_posted(posted):
    posted = list(dict.fromkeys(posted))[-2000:]
    tmp = POSTED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)
    os.replace(tmp, POSTED_FILE)


def score_article(article):
    hits = topic_hits(article)
    priority = SOURCE_PRIORITY.get(article.get("source", ""), 1)
    freshness = 0
    published = article.get("published")
    if published:
        age_hours = max(0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
        freshness = max(0, 48 - age_hours)
    return len(hits) * 10 + priority * 5 + freshness


def select_articles(articles, posted):
    posted_set = set(posted)
    candidates = []
    already = 0

    for article in articles:
        key = article_key(article)
        if key in posted_set:
            already += 1
            continue
        if not is_fresh(article):
            continue
        if not article_is_relevant(article):
            continue
        candidates.append(article)

    candidates.sort(key=score_article, reverse=True)
    print("already posted:", already)
    print("new candidates:", len(candidates))
    return candidates[:MAX_POSTS_PER_RUN]


def telegram(method, payload=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, data=payload or {}, files=files, timeout=TIMEOUT)
        data = response.json()
        if not data.get("ok"):
            print("Telegram error:", data)
            return False, data
        return True, data
    except Exception as exc:
        print("Telegram request error:", exc)
        return False, None


def check_telegram():
    ok, data = telegram("getMe")
    if ok:
        username = data.get("result", {}).get("username", "unknown")
        print("Bot connected:", username)
    return ok


def build_post(article):
    title = clean_text(article["title"])
    source = clean_text(article["source"])
    link = clean_text(article["link"])
    return (
        f"<b>{html.escape(title)}</b>\n\n"
        f"Source: {html.escape(source)}\n"
        f"{html.escape(link)}"
    )


def find_image(page_url):
    try:
        response = requests.get(
            page_url,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MRKNewsBot/7.1)"},
        )
        if response.status_code != 200:
            return None

        base = response.url
        text = response.text
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if not match:
                continue

            image_url = urljoin(base, html.unescape(match.group(1)))
            image = requests.get(
                image_url,
                timeout=TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            content_type = image.headers.get("Content-Type", "").lower()
            if (
                image.status_code == 200
                and image.content
                and len(image.content) <= MAX_IMAGE_SIZE
                and content_type.startswith("image/")
            ):
                return image.content
    except Exception as exc:
        print("image error:", exc)
    return None


def send_post(article):
    text = build_post(article)
    image = find_image(article["link"])

    if image:
        print("Image found.")
        ok, _ = telegram(
            "sendPhoto",
            payload={
                "chat_id": CHANNEL,
                "caption": text,
                "parse_mode": "HTML",
            },
            files={"photo": ("news.jpg", image, "image/jpeg")},
        )
        if ok:
            print("POSTED: image")
            return True
        print("Image send failed. Falling back to text.")
    else:
        print("Image not found.")

    ok, _ = telegram(
        "sendMessage",
        payload={
            "chat_id": CHANNEL,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        },
    )
    if ok:
        print("POSTED: text")
        return True
    return False


def main():
    print("MRK BUSINESS NEWS - VERSION", VERSION)
    print("=" * 60)

    if not BOT_TOKEN:
        print("BOT_TOKEN is missing")
        return

    if not check_telegram():
        print("Telegram check failed")
        return

    posted = load_posted()
    print("posted history:", len(posted))

    articles = fetch_all_feeds()
    print("total RSS articles:", len(articles))

    articles = [a for a in articles if article_is_relevant(a)]
    print("after basic filter:", len(articles))

    articles = deduplicate(articles)
    print("after deduplication:", len(articles))

    selected = select_articles(articles, posted)
    print("to publish:", len(selected))

    if not selected:
        print("Nothing new to publish.")
        return

    published_count = 0
    for article in selected:
        print("\nTITLE:", article["title"])
        print("SOURCE:", article["source"])
        print("LINK:", article["link"])

        if send_post(article):
            posted.append(article_key(article))
            save_posted(posted)
            published_count += 1
        else:
            print("POST FAILED")

    print("\nPublished this run:", published_count)
    print("Done.")


if __name__ == "__main__":
    main()
