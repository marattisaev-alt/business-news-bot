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
# РќРђРЎРўР РћР™РљР
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")

# РЎРєРѕР»СЊРєРѕ РЅРѕРІРѕСЃС‚РµР№ РїСѓР±Р»РёРєРѕРІР°С‚СЊ Р·Р° РѕРґРёРЅ Р·Р°РїСѓСЃРє
MAX_POSTS_PER_RUN = 2

# РњР°РєСЃРёРјР°Р»СЊРЅС‹Р№ РІРѕР·СЂР°СЃС‚ РЅРѕРІРѕСЃС‚Рё
MAX_NEWS_AGE_HOURS = 48

# Р¤Р°Р№Р» СѓР¶Рµ РѕРїСѓР±Р»РёРєРѕРІР°РЅРЅС‹С… РЅРѕРІРѕСЃС‚РµР№
POSTED_FILE = "posted.json"

# РњР°РєСЃРёРјР°Р»СЊРЅС‹Р№ СЂР°Р·РјРµСЂ РєР°СЂС‚РёРЅРєРё
MAX_IMAGE_SIZE = 9 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# =========================================================
# RSS РРЎРўРћР§РќРРљР
# =========================================================

RSS_FEEDS = [
    (
        "Р’РµРґРѕРјРѕСЃС‚Рё вЂ” Р‘РёР·РЅРµСЃ",
        "https://www.vedomosti.ru/rss/rubric/business",
    ),
    (
        "Р’РµРґРѕРјРѕСЃС‚Рё вЂ” Р­РєРѕРЅРѕРјРёРєР°",
        "https://www.vedomosti.ru/rss/rubric/economics",
    ),
    (
        "Р’РµРґРѕРјРѕСЃС‚Рё вЂ” РўРµС…РЅРѕР»РѕРіРёРё",
        "https://www.vedomosti.ru/rss/rubric/technology",
    ),
    (
        "Р’РµРґРѕРјРѕСЃС‚Рё вЂ” РџСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ",
        "https://www.vedomosti.ru/rss/rubric/management/entrepreneurship",
    ),
    (
        "Р’РµРґРѕРјРѕСЃС‚Рё вЂ” Р¤РёРЅР°РЅСЃС‹",
        "https://www.vedomosti.ru/rss/rubric/finance",
    ),
    (
        "Р¦Р‘ Р Р¤ вЂ” РќРѕРІРѕСЃС‚Рё",
        "https://www.cbr.ru/rss/RssNews",
    ),
    (
        "Р¦Р‘ Р Р¤ вЂ” РџСЂРµСЃСЃ-СЂРµР»РёР·С‹",
        "https://www.cbr.ru/rss/RssPress",
    ),
    (
        "RB.RU вЂ” IT",
        "https://rb.ru/feeds/tag/it/",
    ),
    (
        "RB.RU вЂ” AI",
        "https://rb.ru/feeds/tag/ai/",
    ),
    (
        "RB.RU вЂ” E-commerce",
        "https://rb.ru/feeds/tag/ecommerce/",
    ),
]


# =========================================================
# РўР•РњРђРўРРљРђ
# =========================================================

TOPIC_WORDS = {
    # Р‘РёР·РЅРµСЃ
    "Р±РёР·РЅРµСЃ",
    "РєРѕРјРїР°РЅРёСЏ",
    "РєРѕРјРїР°РЅРёРё",
    "РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊ",
    "РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»Рё",
    "РїСЂРµРґРїСЂРёСЏС‚РёРµ",
    "РїСЂРµРґРїСЂРёСЏС‚РёСЏ",
    "РєРѕСЂРїРѕСЂР°С†РёСЏ",
    "РІС‹СЂСѓС‡РєР°",
    "РїСЂРёР±С‹Р»СЊ",
    "СѓР±С‹С‚РѕРє",
    "РёРЅРІРµСЃС‚РёС†РёРё",
    "РёРЅРІРµСЃС‚РѕСЂ",
    "РёРЅРІРµСЃС‚РѕСЂС‹",
    "СЃРґРµР»РєР°",
    "СЃРґРµР»РєРё",
    "СЃР»РёСЏРЅРёРµ",
    "РїРѕРіР»РѕС‰РµРЅРёРµ",
    "СЃС‚Р°СЂС‚Р°Рї",
    "СЃС‚Р°СЂС‚Р°РїС‹",
    "РјСЃРї",
    "РјР°Р»С‹Р№ Р±РёР·РЅРµСЃ",
    "СЃСЂРµРґРЅРёР№ Р±РёР·РЅРµСЃ",
    "СЂРёС‚РµР№Р»",
    "С‚РѕСЂРіРѕРІР»СЏ",
    "РїСЂРѕРёР·РІРѕРґСЃС‚РІРѕ",
    "РїСЂРѕРјС‹С€Р»РµРЅРЅРѕСЃС‚СЊ",
    "СЌРєСЃРїРѕСЂС‚",
    "РёРјРїРѕСЂС‚",
    "Р»РѕРіРёСЃС‚РёРєР°",
    "СЂС‹РЅРѕРє",
    "СЂС‹РЅРєРё",

    # Р­РєРѕРЅРѕРјРёРєР°
    "СЌРєРѕРЅРѕРјРёРєР°",
    "СЌРєРѕРЅРѕРјРёС‡РµСЃРєРёР№",
    "РІРІРї",
    "РёРЅС„Р»СЏС†РёСЏ",
    "РґРµС„Р»СЏС†РёСЏ",
    "СЃС‚Р°РІРєР°",
    "РєР»СЋС‡РµРІР°СЏ СЃС‚Р°РІРєР°",
    "С†РµРЅС‚СЂРѕР±Р°РЅРє",
    "С†РµРЅС‚СЂР°Р»СЊРЅС‹Р№ Р±Р°РЅРє",
    "Р±Р°РЅРє СЂРѕСЃСЃРёРё",
    "РјРёРЅС„РёРЅ",
    "Р±СЋРґР¶РµС‚",
    "РЅР°Р»РѕРіРё",
    "РЅР°Р»РѕРі",
    "РЅРґСЃ",
    "СЂСѓР±Р»СЊ",
    "СЂСѓР±Р»СЏ",
    "СЂСѓР±Р»РµР№",
    "Р·Р°РЅСЏС‚РѕСЃС‚СЊ",
    "Р±РµР·СЂР°Р±РѕС‚РёС†Р°",
    "Р·Р°СЂРїР»Р°С‚Р°",
    "С†РµРЅС‹",
    "РґРѕС…РѕРґС‹",
    "СЂР°СЃС…РѕРґС‹",
    "РєСЂРµРґРёС‚",
    "РєСЂРµРґРёС‚С‹",
    "РёРїРѕС‚РµРєР°",
    "РґРµРЅРµР¶РЅРѕ-РєСЂРµРґРёС‚РЅР°СЏ",
    "РґРµРЅРµР¶РЅР°СЏ РїРѕР»РёС‚РёРєР°",

    # РџСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ
    "РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ",
    "РёРї",
    "СЃР°РјРѕР·Р°РЅСЏС‚С‹Рµ",
    "СЃР°РјРѕР·Р°РЅСЏС‚С‹Р№",
    "Р±РёР·РЅРµСЃРјРµРЅ",
    "Р±РёР·РЅРµСЃРјРµРЅС‹",
    "Р±РёР·РЅРµСЃ-РїСЂРѕРµРєС‚",
    "С„СЂР°РЅС€РёР·Р°",
    "С„СЂР°РЅС€РёР·С‹",
    "РІРµРЅС‡СѓСЂ",
    "РІРµРЅС‡СѓСЂРЅС‹Р№ РєР°РїРёС‚Р°Р»",
    "С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёРµ",
    "РіСЂР°РЅС‚",
    "РіСЂР°РЅС‚С‹",
    "Р°РєСЃРµР»РµСЂР°С‚РѕСЂ",
    "РёРЅРєСѓР±Р°С‚РѕСЂ",

    # РўРµС…РЅРѕР»РѕРіРёРё
    "С‚РµС…РЅРѕР»РѕРіРёРё",
    "С‚РµС…РЅРѕР»РѕРіРёСЏ",
    "Р°Р№С‚Рё",
    "С†РёС„СЂРѕРІРёР·Р°С†РёСЏ",
    "С†РёС„СЂРѕРІРѕР№",
    "РёСЃРєСѓСЃСЃС‚РІРµРЅРЅС‹Р№ РёРЅС‚РµР»Р»РµРєС‚",
    "РЅРµР№СЂРѕСЃРµС‚СЊ",
    "РЅРµР№СЂРѕСЃРµС‚Рё",
    "РјР°С€РёРЅРЅРѕРµ РѕР±СѓС‡РµРЅРёРµ",
    "СЂРѕР±РѕС‚",
    "СЂРѕР±РѕС‚С‹",
    "СЂРѕР±РѕС‚РѕС‚РµС…РЅРёРєР°",
    "РїСЂРѕРіСЂР°РјРјРЅРѕРµ РѕР±РµСЃРїРµС‡РµРЅРёРµ",
    "СЂР°Р·СЂР°Р±РѕС‚РєР°",
    "СЂР°Р·СЂР°Р±РѕС‚С‡РёРє",
    "СЂР°Р·СЂР°Р±РѕС‚С‡РёРєРё",
    "РїСЂРёР»РѕР¶РµРЅРёРµ",
    "РїСЂРёР»РѕР¶РµРЅРёСЏ",
    "СЃРµСЂРІРёСЃ",
    "СЃРµСЂРІРёСЃС‹",
    "РѕР±Р»Р°РєРѕ",
    "РѕР±Р»Р°С‡РЅС‹Р№",
    "РґР°С‚Р°-С†РµРЅС‚СЂ",
    "РґР°С‚Р°-С†РµРЅС‚СЂС‹",
    "РєРёР±РµСЂР±РµР·РѕРїР°СЃРЅРѕСЃС‚СЊ",
    "С‚РµР»РµРєРѕРј",
    "СЃРІСЏР·СЊ",
    "РјРёРєСЂРѕСЃС…РµРјР°",
    "РјРёРєСЂРѕСЃС…РµРјС‹",
    "РїСЂРѕС†РµСЃСЃРѕСЂ",
    "РєРІР°РЅС‚РѕРІС‹Р№",
    "РєРІР°РЅС‚РѕРІС‹Рµ",
    "Р±РёРѕС‚РµС…РЅРѕР»РѕРіРёРё",
    "Р±РµСЃРїРёР»РѕС‚РЅРёРє",
    "Р±РµСЃРїРёР»РѕС‚РЅРёРєРё",
}


# =========================================================
# РњРЈРЎРћР РќР«Р• РўР•РњР«
# =========================================================

LOW_VALUE_WORDS = {
    "СЃРїРѕСЂС‚",
    "С„СѓС‚Р±РѕР»",
    "С…РѕРєРєРµР№",
    "РјР°С‚С‡",
    "РєРёРЅРѕ",
    "РјСѓР·С‹РєР°",
    "С€РѕСѓ",
    "РїРµРІРµС†",
    "РїРµРІРёС†Р°",
    "Р°РєС‚РµСЂ",
    "Р°РєС‚СЂРёСЃР°",
    "РіРѕСЂРѕСЃРєРѕРї",
    "СЂРµС†РµРїС‚",
    "РїРѕРіРѕРґР°",
    "РїСЂРѕРёСЃС€РµСЃС‚РІРёРµ",
    "РєСЂРёРјРёРЅР°Р»",
}


# =========================================================
# РўР•РљРЎРў
# =========================================================

def repair_mojibake(text):
    """РСЃРїСЂР°РІР»СЏРµС‚ С‚РёРїРёС‡РЅС‹Рµ РІР°СЂРёР°РЅС‚С‹ UTF-8 mojibake, РЅРµ РїРѕСЂС‚СЏ РЅРѕСЂРјР°Р»СЊРЅС‹Р№ С‚РµРєСЃС‚."""
    if not text:
        return ""

    value = str(text)

    def bad_score(s):
        markers = (
            "Гђ", "Г‘", "Р ", "РЎ",
            "Гў", "РІР‚", "РІвЂћ",
            "Рѓ", "Р‰", "РЉ", "Сњ", "Сљ", "Сџ",
        )
        return sum(s.count(marker) for marker in markers)

    before = bad_score(value)

    # Р’Р°СЂРёР°РЅС‚ 1: UTF-8 bytes, РѕС€РёР±РѕС‡РЅРѕ РґРµРєРѕРґРёСЂРѕРІР°РЅРЅС‹Рµ РєР°Рє Latin-1.
    try:
        fixed = value.encode("latin1").decode("utf-8")
        if bad_score(fixed) < before:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    # Р’Р°СЂРёР°РЅС‚ 2: UTF-8 bytes, РѕС€РёР±РѕС‡РЅРѕ РґРµРєРѕРґРёСЂРѕРІР°РЅРЅС‹Рµ РєР°Рє Windows-1252.
    try:
        fixed = value.encode("cp1252").decode("utf-8")
        if bad_score(fixed) < before:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    # Р’Р°СЂРёР°РЅС‚ 3: UTF-8 -> Windows-1251/Unicode mojibake
    # Р§Р°СЃС‚С‹Р№ РІРёРґ: "Р СњР С•Р Р†Р С•РЎРѓРЎвЂљР С‘".
    try:
        fixed = value.encode("latin1").decode("utf-8")
        if "Р " in value and ("Р " not in fixed or bad_score(fixed) < before):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return value


def clean_text(text):
    if not text:
        return ""

    text = repair_mojibake(text)
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
    РќР°РґС‘Р¶РЅР°СЏ РїСЂРѕРІРµСЂРєР° СЂСѓСЃСЃРєРѕРіРѕ С‚РµРєСЃС‚Р°.

    Р’Р°Р¶РЅРѕ:
    - РґРѕРїСѓСЃРєР°РµС‚ Р°РЅРіР»РёР№СЃРєРёРµ Р±СЂРµРЅРґС‹ Рё РЅР°Р·РІР°РЅРёСЏ (Ozon, Nvidia, Yandex Cloud);
    - РЅРµ С‚СЂРµР±СѓРµС‚, С‡С‚РѕР±С‹ РєРёСЂРёР»Р»РёС†С‹ Р±С‹Р»Рѕ Р±РѕР»СЊС€Рµ Р»Р°С‚РёРЅРёС†С‹;
    - РѕС‚Р±СЂР°СЃС‹РІР°РµС‚ Р·Р°РіРѕР»РѕРІРєРё Р±РµР· РєРёСЂРёР»Р»РёС†С‹;
    - РґРѕРїСѓСЃРєР°РµС‚ РєРѕСЂРѕС‚РєРёРµ СЂСѓСЃСЃРєРёРµ Р·Р°РіРѕР»РѕРІРєРё.
    """
    text = clean_text(text)

    if not text:
        return False

    cyrillic = len(re.findall(r"[Р°-СЏС‘]", text.lower()))
    latin = len(re.findall(r"[a-z]", text.lower()))
    letters = cyrillic + latin

    if cyrillic == 0:
        return False

    # Р•СЃР»Рё РІ С‚РµРєСЃС‚Рµ РµСЃС‚СЊ С…РѕС‚СЏ Р±С‹ 3 СЂСѓСЃСЃРєРёРµ Р±СѓРєРІС‹,
    # СЃС‡РёС‚Р°РµРј РµРіРѕ СЂСѓСЃСЃРєРёРј. РђРЅРіР»РёР№СЃРєРёРµ Р±СЂРµРЅРґС‹ РЅРµ РјРµС€Р°СЋС‚.
    if cyrillic >= 3:
        return True

    # Р”Р»СЏ РѕС‡РµРЅСЊ РєРѕСЂРѕС‚РєРёС… Р·Р°РіРѕР»РѕРІРєРѕРІ СЂР°Р·СЂРµС€Р°РµРј 1вЂ“2 СЂСѓСЃСЃРєРёРµ Р±СѓРєРІС‹,
    # С‚РѕР»СЊРєРѕ РµСЃР»Рё Р»Р°С‚РёРЅРёС†С‹ РїСЂР°РєС‚РёС‡РµСЃРєРё РЅРµС‚.
    if cyrillic >= 1 and latin == 0 and letters <= 8:
        return True

    return False


def contains_any(text, words):
    text = normalize(text)

    return any(word in text for word in words)


# =========================================================
# РџР РћР’Р•Р РљРђ РќРћР’РћРЎРўР
# =========================================================

def article_is_relevant(article):

    title = article.get("title", "")
    description = article.get("description", "")

    text = normalize(title + " " + description)

    # Р—Р°РіРѕР»РѕРІРѕРє РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЂСѓСЃСЃРєРёРј
    if not is_russian(title):
        print(f"  [FILTER] РќРµ СЂСѓСЃСЃРєРёР№ Р·Р°РіРѕР»РѕРІРѕРє: {title}")
        return False

    # Р”РѕР»Р¶РЅР° Р±С‹С‚СЊ С…РѕС‚СЏ Р±С‹ РѕРґРЅР° Р±РёР·РЅРµСЃ/СЌРєРѕРЅРѕРјРёС‡РµСЃРєР°СЏ/С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєР°СЏ С‚РµРјР°
    if not contains_any(text, TOPIC_WORDS):
        print(f"  [FILTER] РќРµ РїРѕРґС…РѕРґРёС‚ РїРѕ С‚РµРјР°С‚РёРєРµ: {title}")
        return False

    # Р•СЃР»Рё СЏРІРЅРѕ РїСЂРёСЃСѓС‚СЃС‚РІСѓРµС‚ РјСѓСЃРѕСЂРЅР°СЏ С‚РµРјР° вЂ”
    # РїСЂРѕРїСѓСЃРєР°РµРј С‚РѕР»СЊРєРѕ РµСЃР»Рё РµСЃС‚СЊ РЅРµСЃРєРѕР»СЊРєРѕ СЃРёР»СЊРЅС‹С… Р±РёР·РЅРµСЃ-СЃР»РѕРІ
    if contains_any(text, LOW_VALUE_WORDS):

        topic_hits = sum(
            1 for word in TOPIC_WORDS
            if word in text
        )

        if topic_hits < 2:
            print(f"  [FILTER] РњСѓСЃРѕСЂРЅР°СЏ С‚РµРјР°: {title}")
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
# Р”РђРўР«
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

        # РРЅРѕРіРґР° РІСЃС‚СЂРµС‡Р°РµС‚СЃСЏ ISO РґР°С‚Р°
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
        # Р•СЃР»Рё РёСЃС‚РѕС‡РЅРёРє РЅРµ РґР°Р» РґР°С‚Сѓ,
        # РЅРµ РѕС‚Р±СЂР°СЃС‹РІР°РµРј Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё.
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
    # IMPORTANT:
    # Parse RSS from raw bytes. This lets XML itself determine UTF-8/Windows-1251
    # from its encoding declaration and prevents "Гђ..." mojibake.


    articles = []

    try:

        root = ET.fromstring(xml_text)

    except Exception as e:

        print(
            f"[RSS PARSE ERROR] {source}: {e}"
        )

        return articles

    items = root.findall(
        ".//item"
    )

    # РџРѕРґРґРµСЂР¶РєР° Atom
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
                "  -> РёСЃС‚РѕС‡РЅРёРє РЅРµРґРѕСЃС‚СѓРїРµРЅ"
            )

            continue

        print(
            f"  -> HTTP {response.status_code}"
        )

        articles = parse_rss(
            response.content,
            source
        )

        print(
            f"  -> РїРѕР»СѓС‡РµРЅРѕ: {len(articles)}"
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
            f"  -> РїРѕРґС…РѕРґРёС‚: {accepted}"
        )

    print(
        f"\nР’СЃРµРіРѕ РїРѕРґС…РѕРґСЏС‰РёС… РЅРѕРІРѕСЃС‚РµР№: {len(all_articles)}"
    )

    return all_articles


# =========================================================
# Р”Р•Р”РЈРџР›РРљРђР¦РРЇ
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
        r"[Р°-СЏС‘a-z0-9]{4,}",
        normalize(text)
    )

    stop_words = {
        "Р±РёР·РЅРµСЃ",
        "РєРѕРјРїР°РЅРёСЏ",
        "РєРѕРјРїР°РЅРёРё",
        "СЂРѕСЃСЃРёСЏ",
        "СЂРѕСЃСЃРёР№СЃРєРёР№",
        "СЂРѕСЃСЃРёР№СЃРєРёРµ",
        "РЅРѕРІРѕСЃС‚Рё",
        "РєРѕС‚РѕСЂС‹Рµ",
        "РєРѕС‚РѕСЂС‹Р№",
        "РєРѕС‚РѕСЂС‹С…",
        "С‚Р°РєР¶Рµ",
        "РїРѕСЃР»Рµ",
        "Р±СѓРґРµС‚",
        "Р±СѓРґСѓС‚",
        "СЌС‚РѕС‚",
        "СЌС‚РѕРіРѕ",
        "СЃРІРѕРµРіРѕ",
        "СЃРІРѕРё",
        "РјРѕР¶РµС‚",
        "РјРѕРіСѓС‚",
        "СЃС‚Р°Р»Рѕ",
        "СЃС‚Р°Р»Рё",
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
        f"РџРѕСЃР»Рµ РґРµРґСѓРїР»РёРєР°С†РёРё: {len(result)}"
    )

    return result


# =========================================================
# РћР¦Р•РќРљРђ РќРћР’РћРЎРўР
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

    # РўРµРјР°С‚РёС‡РµСЃРєРёРµ СЃРѕРІРїР°РґРµРЅРёСЏ
    for word in TOPIC_WORDS:

        if word in text:
            score += 1

    # РЎРІРµР¶РµСЃС‚СЊ
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

    # РџСЂРёРѕСЂРёС‚РµС‚ РёСЃС‚РѕС‡РЅРёРєРѕРІ
    source = normalize(
        article.get(
            "source",
            ""
        )
    )

    if "РІРµРґРѕРјРѕСЃС‚Рё" in source:
        score += 5

    elif "С†Р± СЂС„" in source:
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
    already_posted = 0

    for article in articles:

        key = article_key(
            article
        )

        if key in posted_set:
            already_posted += 1
            continue

        candidates.append(
            article
        )

    print(f"РЈР¶Рµ Р±С‹Р»Рё РѕРїСѓР±Р»РёРєРѕРІР°РЅС‹: {already_posted}")

    candidates.sort(
        key=topic_score,
        reverse=True
    )

    print(
        f"РќРѕРІС‹С… РєР°РЅРґРёРґР°С‚РѕРІ: {len(candidates)}"
    )

    return candidates[
        :MAX_POSTS_PER_RUN
    ]


# =========================================================
# Р—РђР“РћР›РћР’РћРљ
# =========================================================

def clean_title(title):

    title = clean_text(
        title
    )

    # РЈРґР°Р»СЏРµРј РЅР°Р·РІР°РЅРёРµ РёСЃС‚РѕС‡РЅРёРєР° РІ РєРѕРЅС†Рµ
    title = re.sub(
        r"\s+[вЂ”вЂ“-]\s+(Р’РµРґРѕРјРѕСЃС‚Рё|Р Р‘Рљ|RB\.RU|Р¦Р‘ Р Р¤)\s*$",
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
# РљРђР РўРРќРљРђ
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
            f"Р‘РѕС‚ РїРѕРґРєР»СЋС‡РµРЅ: "
            f"@{bot.get('username')}"
        )

        return True

    except Exception as e:

        print(
            f"РћС€РёР±РєР° Telegram: {e}"
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
# РџРћРЎРў
# =========================================================

def build_post(article):

    title = clean_title(
        article.get(
            "title",
            "РќРѕРІРѕСЃС‚СЊ"
        )
    )

    source = clean_text(
        article.get(
            "source",
            "РСЃС‚РѕС‡РЅРёРє"
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
        f"рџ“° <b>{title}</b>\n\n"
        f"РСЃС‚РѕС‡РЅРёРє: {source}\n"
        f'рџ”— <a href="{link}">'
        f"Р§РёС‚Р°С‚СЊ РёСЃС‚РѕС‡РЅРёРє"
        f"</a>"
    )


# =========================================================
# РџР РћР’Р•Р РљРђ
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
        "РњР Рљ [Р‘РР—РќР•РЎ РќРћР’РћРЎРўР] вЂ” VERSION 6.4"
    )

    print(
        "=========================================="
    )

    # РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ
    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN РЅРµ Р·Р°РґР°РЅ."
        )

    if not CHANNEL:

        raise RuntimeError(
            "CHANNEL РЅРµ Р·Р°РґР°РЅ."
        )

    print(
        f"РљР°РЅР°Р»: {CHANNEL}"
    )

    print(
        f"РњР°РєСЃРёРјСѓРј РїРѕСЃС‚РѕРІ: "
        f"{MAX_POSTS_PER_RUN}"
    )

    print(
        f"Р’РѕР·СЂР°СЃС‚ РЅРѕРІРѕСЃС‚Рё: "
        f"{MAX_NEWS_AGE_HOURS} С‡Р°СЃРѕРІ"
    )

    # РџСЂРѕРІРµСЂСЏРµРј Telegram
    if not check_telegram():

        raise RuntimeError(
            "Telegram API РЅРµРґРѕСЃС‚СѓРїРµРЅ."
        )

    # Р—Р°РіСЂСѓР¶Р°РµРј РёСЃС‚РѕСЂРёСЋ
    posted = load_posted()

    print(
        f"РЈР¶Рµ РѕРїСѓР±Р»РёРєРѕРІР°РЅРѕ РІ РёСЃС‚РѕСЂРёРё: "
        f"{len(posted)}"
    )

    # РџРѕР»СѓС‡Р°РµРј РЅРѕРІРѕСЃС‚Рё
    articles = fetch_all_feeds()

    print(
        "\n=========================================="
    )

    print(
        f"Р’СЃРµРіРѕ РїРѕРґС…РѕРґСЏС‰РёС… РЅРѕРІРѕСЃС‚РµР№: "
        f"{len(articles)}"
    )

    print(
        "=========================================="
    )

    if not articles:

        print(
            "РџРѕРґС…РѕРґСЏС‰РёС… РЅРѕРІРѕСЃС‚РµР№ РЅРµС‚."
        )

        return

    # Р”СѓР±Р»Рё
    articles = remove_duplicates(
        articles
    )

    # Р’С‹Р±РѕСЂ
    selected = select_articles(
        articles,
        posted
    )

    print(
        f"Рљ РїСѓР±Р»РёРєР°С†РёРё: "
        f"{len(selected)}"
    )

    if not selected:

        print(
            "Р’СЃРµ РЅР°Р№РґРµРЅРЅС‹Рµ РЅРѕРІРѕСЃС‚Рё СѓР¶Рµ РїСѓР±Р»РёРєРѕРІР°Р»РёСЃСЊ."
        )

        return

    # РџСѓР±Р»РёРєР°С†РёСЏ
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
            f"Р—Р°РіРѕР»РѕРІРѕРє: {title}"
        )

        print(
            f"РСЃС‚РѕС‡РЅРёРє: {source}"
        )

        print(
            f"РЎСЃС‹Р»РєР°: {link}"
        )

        post = build_post(
            article
        )

        if not quality_check(
            article,
            post
        ):

            print(
                "РџСЂРѕРїСѓСЃРє: quality check"
            )

            continue

        try:

            print(
                "РС‰Сѓ РёР·РѕР±СЂР°Р¶РµРЅРёРµ..."
            )

            image = find_image(
                link
            )

            if image:

                print(
                    "РР·РѕР±СЂР°Р¶РµРЅРёРµ РЅР°Р№РґРµРЅРѕ."
                )

                send_photo(
                    image,
                    post
                )

                print(
                    "вњ… РћРїСѓР±Р»РёРєРѕРІР°РЅРѕ СЃ РёР·РѕР±СЂР°Р¶РµРЅРёРµРј."
                )

            else:

                print(
                    "РР·РѕР±СЂР°Р¶РµРЅРёРµ РЅРµ РЅР°Р№РґРµРЅРѕ."
                )

                send_message(
                    post
                )

                print(
                    "вњ… РћРїСѓР±Р»РёРєРѕРІР°РЅРѕ Р±РµР· РёР·РѕР±СЂР°Р¶РµРЅРёСЏ."
                )

            # Р—Р°РїРёСЃС‹РІР°РµРј С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РїСѓР±Р»РёРєР°С†РёРё
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
                "вќЊ РћРЁРР‘РљРђ РџРЈР‘Р›РРљРђР¦РР:"
            )

            print(
                repr(e)
            )

    print(
        "\n=========================================="
    )

    print(
        "Р“РћРўРћР’Рћ."
    )

    print(
        "=========================================="
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
