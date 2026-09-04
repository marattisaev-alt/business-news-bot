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
# РќРђРЎРўР РћР™РљР
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@etomrk")

# РЎРєРѕР»СЊРєРѕ РЅРѕРІРѕСЃС‚РµР№ РїСѓР±Р»РёРєРѕРІР°С‚СЊ Р·Р° РѕРґРёРЅ Р·Р°РїСѓСЃРє
MAX_POSTS_PER_RUN = 2

# Р‘РµСЂС‘Рј РЅРѕРІРѕСЃС‚Рё РЅРµ СЃС‚Р°СЂС€Рµ СЌС‚РѕРіРѕ РєРѕР»РёС‡РµСЃС‚РІР° С‡Р°СЃРѕРІ
MAX_NEWS_AGE_HOURS = 48

# РќРµ РїСѓР±Р»РёРєРѕРІР°С‚СЊ РѕРґРёРЅ Рё С‚РѕС‚ Р¶Рµ РјР°С‚РµСЂРёР°Р» РїРѕРІС‚РѕСЂРЅРѕ
POSTED_FILE = "posted.json"

# РњР°РєСЃРёРјР°Р»СЊРЅС‹Р№ СЂР°Р·РјРµСЂ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
MAX_IMAGE_SIZE = 9 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# =========================================================
# Р РћРЎРЎРР™РЎРљРР• RSS-РРЎРўРћР§РќРРљР
# =========================================================
#
# РСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ РїСЂСЏРјС‹Рµ RSS-Р»РµРЅС‚С‹ СЂРѕСЃСЃРёР№СЃРєРёС… РёСЃС‚РѕС‡РЅРёРєРѕРІ.
# РќРёРєР°РєРёС… Р°РЅРіР»РёР№СЃРєРёС… Google News / Reuters / USA feeds.
#
# Р’РµРґРѕРјРѕСЃС‚Рё РѕС„РёС†РёР°Р»СЊРЅРѕ РїСѓР±Р»РёРєСѓСЋС‚ RSS РґР»СЏ Р±РёР·РЅРµСЃР°, СЌРєРѕРЅРѕРјРёРєРё,
# С‚РµС…РЅРѕР»РѕРіРёР№ Рё РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІР°.
#
# Р¦Р‘ Р Р¤ вЂ” РѕС„РёС†РёР°Р»СЊРЅС‹Р№ СЂРѕСЃСЃРёР№СЃРєРёР№ РёСЃС‚РѕС‡РЅРёРє СЌРєРѕРЅРѕРјРёС‡РµСЃРєРёС…
# Рё С„РёРЅР°РЅСЃРѕРІС‹С… РЅРѕРІРѕСЃС‚РµР№.
#
# RB.RU вЂ” СЂРѕСЃСЃРёР№СЃРєРѕРµ РґРµР»РѕРІРѕРµ/С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєРѕРµ РёР·РґР°РЅРёРµ.
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
# Р¤РР›Р¬РўР  РўР•РњРђРўРРљР
# =========================================================

# РњР°С‚РµСЂРёР°Р» РґРѕР»Р¶РµРЅ РѕС‚РЅРѕСЃРёС‚СЊСЃСЏ С…РѕС‚СЏ Р±С‹ Рє РѕРґРЅРѕР№ РёР· С‡РµС‚С‹СЂС‘С…
# РЅСѓР¶РЅС‹С… С‚РµРј: Р±РёР·РЅРµСЃ, СЌРєРѕРЅРѕРјРёРєР°, РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ, С‚РµС…РЅРѕР»РѕРіРёРё.

TOPIC_WORDS = {
    # Р‘РёР·РЅРµСЃ
    "Р±РёР·РЅРµСЃ", "РєРѕРјРїР°РЅРёСЏ", "РєРѕРјРїР°РЅРёРё", "РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊ", "РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»Рё",
    "РїСЂРµРґРїСЂРёСЏС‚РёРµ", "РїСЂРµРґРїСЂРёСЏС‚РёСЏ", "РєРѕСЂРїРѕСЂР°С†РёСЏ", "РєРѕСЂРїРѕСЂР°С‚РёРІРЅС‹Р№",
    "РІС‹СЂСѓС‡РєР°", "РїСЂРёР±С‹Р»СЊ", "СѓР±С‹С‚РѕРє", "РёРЅРІРµСЃС‚РёС†РёРё", "РёРЅРІРµСЃС‚РѕСЂ",
    "РёРЅРІРµСЃС‚РѕСЂС‹", "СЃРґРµР»РєР°", "СЃРґРµР»РєРё", "СЃР»РёСЏРЅРёРµ", "РїРѕРіР»РѕС‰РµРЅРёРµ",
    "СЃС‚Р°СЂС‚Р°Рї", "СЃС‚Р°СЂС‚Р°РїС‹", "РјСЃРї", "РјР°Р»С‹Р№ Р±РёР·РЅРµСЃ", "СЃСЂРµРґРЅРёР№ Р±РёР·РЅРµСЃ",
    "СЂРёС‚РµР№Р»", "С‚РѕСЂРіРѕРІР»СЏ", "РїСЂРѕРёР·РІРѕРґСЃС‚РІРѕ", "РїСЂРѕРјС‹С€Р»РµРЅРЅРѕСЃС‚СЊ",
    "СЌРєСЃРїРѕСЂС‚", "РёРјРїРѕСЂС‚", "Р»РѕРіРёСЃС‚РёРєР°", "СЂС‹РЅРѕРє",

    # Р­РєРѕРЅРѕРјРёРєР°
    "СЌРєРѕРЅРѕРјРёРєР°", "СЌРєРѕРЅРѕРјРёС‡РµСЃРєРёР№", "РІРІРї", "РёРЅС„Р»СЏС†РёСЏ", "РґРµС„Р»СЏС†РёСЏ",
    "СЃС‚Р°РІРєР°", "РєР»СЋС‡РµРІР°СЏ СЃС‚Р°РІРєР°", "С†РµРЅС‚СЂРѕР±Р°РЅРє", "Р±Р°РЅРє СЂРѕСЃСЃРёРё",
    "РјРёРЅС„РёРЅ", "Р±СЋРґР¶РµС‚", "РЅР°Р»РѕРіРё", "РЅР°Р»РѕРі", "РЅРґСЃ", "СЂСѓР±Р»СЊ",
    "СЂСѓР±Р»СЏ", "СЂСѓР±Р»РµР№", "Р·Р°РЅСЏС‚РѕСЃС‚СЊ", "Р±РµР·СЂР°Р±РѕС‚РёС†Р°", "Р·Р°СЂРїР»Р°С‚Р°",
    "С†РµРЅС‹", "РґРѕС…РѕРґС‹", "СЂР°СЃС…РѕРґС‹", "РєСЂРµРґРёС‚", "РєСЂРµРґРёС‚С‹", "РёРїРѕС‚РµРєР°",
    "РґРµРЅРµР¶РЅРѕ-РєСЂРµРґРёС‚РЅР°СЏ", "РґРµРЅРµР¶РЅР°СЏ РїРѕР»РёС‚РёРєР°",

    # РџСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ
    "РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ", "РёРї", "СЃР°РјРѕР·Р°РЅСЏС‚С‹Рµ", "СЃР°РјРѕР·Р°РЅСЏС‚С‹Р№",
    "Р±РёР·РЅРµСЃРјРµРЅ", "Р±РёР·РЅРµСЃРјРµРЅС‹", "Р±РёР·РЅРµСЃ-РїСЂРѕРµРєС‚", "С„СЂР°РЅС€РёР·Р°",
    "С„СЂР°РЅС€РёР·С‹", "РІРµРЅС‡СѓСЂ", "РІРµРЅС‡СѓСЂРЅС‹Р№ РєР°РїРёС‚Р°Р»", "С„РёРЅР°РЅСЃРёСЂРѕРІР°РЅРёРµ",
    "РіСЂР°РЅС‚", "РіСЂР°РЅС‚С‹", "Р°РєСЃРµР»РµСЂР°С‚РѕСЂ", "РёРЅРєСѓР±Р°С‚РѕСЂ",

    # РўРµС…РЅРѕР»РѕРіРёРё
    "С‚РµС…РЅРѕР»РѕРіРёРё", "С‚РµС…РЅРѕР»РѕРіРёСЏ", "РёС‚", "Р°Р№С‚Рё", "С†РёС„СЂРѕРІРёР·Р°С†РёСЏ",
    "С†РёС„СЂРѕРІРѕР№", "РёСЃРєСѓСЃСЃС‚РІРµРЅРЅС‹Р№ РёРЅС‚РµР»Р»РµРєС‚", "РёРё", "РЅРµР№СЂРѕСЃРµС‚СЊ",
    "РЅРµР№СЂРѕСЃРµС‚Рё", "РјР°С€РёРЅРЅРѕРµ РѕР±СѓС‡РµРЅРёРµ", "СЂРѕР±РѕС‚", "СЂРѕР±РѕС‚С‹",
    "СЂРѕР±РѕС‚РѕС‚РµС…РЅРёРєР°", "РїСЂРѕРіСЂР°РјРјРЅРѕРµ РѕР±РµСЃРїРµС‡РµРЅРёРµ", "РїРѕ",
    "СЂР°Р·СЂР°Р±РѕС‚РєР°", "СЂР°Р·СЂР°Р±РѕС‚С‡РёРє", "СЂР°Р·СЂР°Р±РѕС‚С‡РёРєРё", "РїСЂРёР»РѕР¶РµРЅРёРµ",
    "РїСЂРёР»РѕР¶РµРЅРёСЏ", "СЃРµСЂРІРёСЃ", "СЃРµСЂРІРёСЃС‹", "РѕР±Р»Р°РєРѕ", "РѕР±Р»Р°С‡РЅС‹Р№",
    "РґР°С‚Р°-С†РµРЅС‚СЂ", "РґР°С‚Р°-С†РµРЅС‚СЂС‹", "РєРёР±РµСЂР±РµР·РѕРїР°СЃРЅРѕСЃС‚СЊ", "С‚РµР»РµРєРѕРј",
    "СЃРІСЏР·СЊ", "РјРёРєСЂРѕСЃС…РµРјР°", "РјРёРєСЂРѕСЃС…РµРјС‹", "РїСЂРѕС†РµСЃСЃРѕСЂ",
    "РєРІР°РЅС‚РѕРІС‹Р№", "РєРІР°РЅС‚РѕРІС‹Рµ", "Р±РёРѕС‚РµС…РЅРѕР»РѕРіРёРё", "Р±РµСЃРїРёР»РѕС‚РЅРёРє",
    "Р±РµСЃРїРёР»РѕС‚РЅРёРєРё",
}

# РњР°С‚РµСЂРёР°Р» РґРѕР»Р¶РµРЅ РёРјРµС‚СЊ СЂРѕСЃСЃРёР№СЃРєРёР№ РєРѕРЅС‚РµРєСЃС‚.
# Р­С‚Рѕ Р·Р°С‰РёС‰Р°РµС‚ РєР°РЅР°Р» РѕС‚ СЃР»СѓС‡Р°Р№РЅС‹С… РјРёСЂРѕРІС‹С… РЅРѕРІРѕСЃС‚РµР№ РёР· RSS.
RUSSIA_WORDS = {
    "СЂРѕСЃСЃРёСЏ", "СЂРѕСЃСЃРёРё", "СЂРѕСЃСЃРёСЋ", "СЂРѕСЃСЃРёР№СЃРєРёР№", "СЂРѕСЃСЃРёР№СЃРєР°СЏ",
    "СЂРѕСЃСЃРёР№СЃРєРёРµ", "СЂРѕСЃСЃРёР№СЃРєРѕРіРѕ", "СЂС„", "РјРѕСЃРєРІР°", "РјРѕСЃРєРѕРІСЃРєР°СЏ",
    "СЃР°РЅРєС‚-РїРµС‚РµСЂР±СѓСЂРі", "РїРµС‚РµСЂР±СѓСЂРі", "РїРёС‚РµСЂ", "РєР°Р·Р°РЅСЊ",
    "РЅРѕРІРѕСЃРёР±РёСЂСЃРє", "РµРєР°С‚РµСЂРёРЅР±СѓСЂРі", "РЅРёР¶РЅРёР№ РЅРѕРІРіРѕСЂРѕРґ", "РєСЂР°СЃРЅРѕРґР°СЂ",
    "СЂРѕСЃС‚РѕРІ", "РІР»Р°РґРёРІРѕСЃС‚РѕРє", "С…Р°Р±Р°СЂРѕРІСЃРє", "СЃРѕС‡Рё", "СЃР°РјР°СЂР°",
    "С‚Р°С‚Р°СЂСЃС‚Р°РЅ", "РґР°РіРµСЃС‚Р°РЅ", "С‡РµС‡РЅСЏ", "СѓСЂР°Р»", "СЃРёР±РёСЂСЊ",
    "РґР°Р»СЊРЅРёР№ РІРѕСЃС‚РѕРє", "РєСЂС‹Рј", "СЂСѓР±Р»СЊ", "СЂСѓР±Р»СЏ", "СЂСѓР±Р»РµР№",
    "РјРѕСЃР±РёСЂР¶Р°", "РјРѕСЃРєРѕРІСЃРєР°СЏ Р±РёСЂР¶Р°", "СЃР±РµСЂ", "СЃР±РµСЂР±Р°РЅРє", "РІС‚Р±",
    "РіР°Р·РїСЂРѕРј", "СЂРѕСЃРЅРµС„С‚СЊ", "Р»СѓРєРѕР№Р»", "СЏРЅРґРµРєСЃ", "РѕР·РѕРЅ",
    "ozon", "wildberries", "Р°РІРёС‚Рѕ", "РІРє", "СЂРѕСЃС‚РµР»РµРєРѕРј",
    "РјС‚СЃ", "РјРµРіР°С„РѕРЅ", "Р±РёР»Р°Р№РЅ", "С‚РёРЅСЊРєРѕС„С„", "Р°Р»СЊС„Р°-Р±Р°РЅРє",
    "СЃРѕРІРєРѕРјР±Р°РЅРє", "РЅРѕРІР°С‚СЌРє", "СЂСѓСЃР°Р»", "СЃРµРІРµСЂСЃС‚Р°Р»СЊ",
    "РјР°РіРЅРёС‚", "РїСЏС‚РµСЂРѕС‡РєР°", "x5", "СЂР¶Рґ", "Р°СЌСЂРѕС„Р»РѕС‚",
    "СЂРѕСЃР°С‚РѕРј", "СЂРѕСЃС‚РµС…", "СЂРѕСЃРєРѕСЃРјРѕСЃ", "СЏРЅРґРµРєСЃ", "РєР°СЃРїРµСЂСЃРєРёР№",
    "1СЃ", "Р°СЃРє", "РјРёРЅС„РёРЅ", "РјРёРЅСЌРєРѕРЅРѕРјСЂР°Р·РІРёС‚РёСЏ", "РјРёРЅС†РёС„СЂС‹",
    "С†РµРЅС‚СЂРѕР±Р°РЅРє", "Р±Р°РЅРє СЂРѕСЃСЃРёРё", "С„РЅСЃ", "РїСЂР°РІРёС‚РµР»СЊСЃС‚РІРѕ СЂРѕСЃСЃРёРё",
    "РіРѕСЃРґСѓРјР°", "С„РµРґРµСЂР°Р»СЊРЅР°СЏ РЅР°Р»РѕРіРѕРІР°СЏ СЃР»СѓР¶Р±Р°",
}

LOW_VALUE_WORDS = {
    "СЃРїРѕСЂС‚", "С„СѓС‚Р±РѕР»", "С…РѕРєРєРµР№", "РјР°С‚С‡", "РєРёРЅРѕ", "РјСѓР·С‹РєР°",
    "С€РѕСѓ", "РїРµРІРµС†", "РїРµРІРёС†Р°", "Р°РєС‚РµСЂ", "Р°РєС‚СЂРёСЃР°", "Р·РЅР°РјРµРЅРёС‚РѕСЃС‚СЊ",
    "РіРѕСЂРѕСЃРєРѕРї", "СЂРµС†РµРїС‚", "РїРѕРіРѕРґР°", "РїСЂРѕРёСЃС€РµСЃС‚РІРёРµ", "РєСЂРёРјРёРЅР°Р»",
}


# =========================================================
# Р‘РђР—РћР’Р«Р• Р¤РЈРќРљР¦РР
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

    cyrillic = len(re.findall(r"[Р°-СЏС‘]", text.lower()))
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

    # РўРѕР»СЊРєРѕ СЂСѓСЃСЃРєРѕСЏР·С‹С‡РЅС‹Рµ РјР°С‚РµСЂРёР°Р»С‹.
    if not is_russian(title):
        return False

    # РўРѕР»СЊРєРѕ РѕРґРЅР° РёР· РЅСѓР¶РЅС‹С… С‚РµРј.
    if not contains_any(text, TOPIC_WORDS):
        return False

    # Р”Р»СЏ СЂРѕСЃСЃРёР№СЃРєРѕРіРѕ РєР°РЅР°Р»Р° РЅСѓР¶РµРЅ СЂРѕСЃСЃРёР№СЃРєРёР№ РєРѕРЅС‚РµРєСЃС‚.
    if not contains_any(text, RUSSIA_WORDS):
        return False

    # РћС‚СЃРµРєР°РµРј РѕС‡РµРІРёРґРЅС‹Р№ РѕС„С„С‚РѕРї.
    if contains_any(text, LOW_VALUE_WORDS):
        # РќРµ РѕС‚Р±СЂР°СЃС‹РІР°РµРј РјР°С‚РµСЂРёР°Р», РµСЃР»Рё РІ РЅС‘Рј РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ
        # СЏРІРЅРѕ РµСЃС‚СЊ Р±РёР·РЅРµСЃ/СЌРєРѕРЅРѕРјРёРєР°/С‚РµС…РЅРѕР»РѕРіРёРё Рё Р РѕСЃСЃРёСЏ.
        # Р—РґРµСЃСЊ С‚РѕР»СЊРєРѕ РјСЏРіРєР°СЏ РїСЂРѕРІРµСЂРєР°.
        topic_hits = sum(1 for word in TOPIC_WORDS if word in text)
        if topic_hits < 2:
            return False

    return True


# =========================================================
# РРЎРўРћР РРЇ
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
# Р”РђРўР«
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
        # Р•СЃР»Рё РёСЃС‚РѕС‡РЅРёРє РЅРµ РґР°Р» РґР°С‚Сѓ, РјР°С‚РµСЂРёР°Р» Р»СѓС‡С€Рµ РЅРµ Р±СЂР°С‚СЊ.
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

        # РќРµРєРѕС‚РѕСЂС‹Рµ RSS РёСЃРїРѕР»СЊР·СѓСЋС‚ dc:date.
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

        print(f"  РЅР°Р№РґРµРЅРѕ: {len(articles)}")

        for article in articles:
            if age_hours(article.get("published")) > MAX_NEWS_AGE_HOURS:
                continue

            if not article_is_relevant(article):
                continue

            all_articles.append(article)

    return all_articles


# =========================================================
# Р”Р•Р”РЈРџР›РРљРђР¦РРЇ
# =========================================================

def normalize_link(link):
    link = clean_text(link)

    try:
        parsed = urlparse(link)

        # РЈР±РёСЂР°РµРј СЃС‚Р°РЅРґР°СЂС‚РЅС‹Рµ tracking-РїР°СЂР°РјРµС‚СЂС‹.
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
    words = re.findall(r"[Р°-СЏС‘a-z0-9]{4,}", normalize(text))

    stop_words = {
        "Р±РёР·РЅРµСЃ", "РєРѕРјРїР°РЅРёСЏ", "РєРѕРјРїР°РЅРёРё", "СЂРѕСЃСЃРёСЏ", "СЂРѕСЃСЃРёР№СЃРєРёР№",
        "РЅРѕРІРѕСЃС‚Рё", "РєРѕС‚РѕСЂС‹Рµ", "РєРѕС‚РѕСЂС‹Р№", "РєРѕС‚РѕСЂС‹С…", "С‚Р°РєР¶Рµ",
        "РїРѕСЃР»Рµ", "Р±СѓРґРµС‚", "Р±СѓРґСѓС‚", "СЌС‚РѕС‚", "СЌС‚РѕРіРѕ", "СЃРІРѕРµРіРѕ",
        "СЃРІРѕРё", "РјРѕР¶РµС‚", "РјРѕРіСѓС‚", "СЃС‚Р°Р»Рѕ", "СЃС‚Р°Р»Рё",
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

    # РЎРЅР°С‡Р°Р»Р° СЃРѕСЂС‚РёСЂСѓРµРј РѕС‚ РЅРѕРІС‹С… Рє СЃС‚Р°СЂС‹Рј.
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
# Р’Р«Р‘РћР  РќРћР’РћРЎРўР•Р™
# =========================================================

def topic_score(article):
    text = normalize(
        article.get("title", "") + " " + article.get("description", "")
    )

    score = 0

    # Р§РµРј Р±РѕР»СЊС€Рµ РїСЂСЏРјС‹С… СЃРѕРІРїР°РґРµРЅРёР№ СЃ РЅСѓР¶РЅС‹РјРё С‚РµРјР°РјРё,
    # С‚РµРј РІС‹С€Рµ РјР°С‚РµСЂРёР°Р» РІ РѕС‡РµСЂРµРґРё.
    for word in TOPIC_WORDS:
        if word in text:
            score += 1

    # Р РѕСЃСЃРёР№СЃРєРёР№ РєРѕРЅС‚РµРєСЃС‚.
    for word in RUSSIA_WORDS:
        if word in text:
            score += 2

    # РЎРІРµР¶РµСЃС‚СЊ.
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

    # РџСЂРёРѕСЂРёС‚РµС‚ РїСЂСЏРјС‹Рј РґРµР»РѕРІС‹Рј РёСЃС‚РѕС‡РЅРёРєР°Рј.
    source = normalize(article.get("source", ""))

    if "РІРµРґРѕРјРѕСЃС‚Рё" in source:
        score += 5
    elif "С†Р± СЂС„" in source:
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
# Р—РђР“РћР›РћР’РћРљ
# =========================================================

def clean_title(title):
    title = clean_text(title)

    # РЈР±РёСЂР°РµРј С…РІРѕСЃС‚С‹ РІРёРґР° "вЂ” Р’РµРґРѕРјРѕСЃС‚Рё".
    title = re.sub(
        r"\s+[вЂ”-]\s+(Р’РµРґРѕРјРѕСЃС‚Рё|Р Р‘Рљ|RB\.RU|Р¦Р‘ Р Р¤)\s*$",
        "",
        title,
        flags=re.I,
    )

    # РЈР±РёСЂР°РµРј Р»РёС€РЅРёРµ РїСЂРѕР±РµР»С‹.
    title = re.sub(r"\s+", " ", title).strip()

    return title


# =========================================================
# РР—РћР‘Р РђР–Р•РќРР•
# =========================================================

def find_image(url):
    """
    РџС‹С‚Р°РµРјСЃСЏ РІР·СЏС‚СЊ og:image СЃРѕ СЃС‚СЂР°РЅРёС†С‹ РёСЃС‚РѕС‡РЅРёРєР°.
    Р•СЃР»Рё РёР·РѕР±СЂР°Р¶РµРЅРёРµ РЅРµРґРѕСЃС‚СѓРїРЅРѕ, РЅРѕРІРѕСЃС‚СЊ РІСЃС‘ СЂР°РІРЅРѕ РїСѓР±Р»РёРєСѓРµС‚СЃСЏ
    РѕР±С‹С‡РЅС‹Рј С‚РµРєСЃС‚РѕРј.
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
# Р¤РћР РњРђРў РџРћРЎРўРђ
# =========================================================
#
# Р’РђР–РќРћ:
# Р—РґРµСЃСЊ СЃРїРµС†РёР°Р»СЊРЅРѕ РќР•Рў:
# - "РџРѕС‡РµРјСѓ СЌС‚Рѕ РІР°Р¶РЅРѕ"
# - РєР°С‚РµРіРѕСЂРёРё
# - СЂС‹РЅРєР°
# - РєСЂР°С‚РєРѕРіРѕ РѕРїРёСЃР°РЅРёСЏ
# - Р°РЅР°Р»РёР·Р°
# - С…СЌС€С‚РµРіРѕРІ
# - РєРѕС‚РёСЂРѕРІРѕРє
# - РєСѓСЂСЃРѕРІ РІР°Р»СЋС‚
# - РїРµСЂРµРІРѕРґР° С‡РµСЂРµР· СЃС‚РѕСЂРѕРЅРЅРёР№ СЃРµСЂРІРёСЃ
#
# РўРѕР»СЊРєРѕ:
# Р·Р°РіРѕР»РѕРІРѕРє
# РёСЃС‚РѕС‡РЅРёРє
# СЃСЃС‹Р»РєР°
# =========================================================

def build_post(article):
    title = clean_title(article.get("title", "РќРѕРІРѕСЃС‚СЊ"))
    source = clean_text(article.get("source", "РСЃС‚РѕС‡РЅРёРє"))
    link = normalize_link(article.get("link", ""))

    title = escape_html(title)
    source = escape_html(source)
    link = escape_html(link)

    return (
        f"рџ“° <b>{title}</b>\n\n"
        f"РСЃС‚РѕС‡РЅРёРє: {source}\n"
        f"рџ”— <a href=\"{link}\">Р§РёС‚Р°С‚СЊ РёСЃС‚РѕС‡РЅРёРє</a>"
    )


# =========================================================
# РџР РћР’Р•Р РљРђ
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
# РћРЎРќРћР’РќРђРЇ Р›РћР“РРљРђ
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "РќРµ Р·Р°РґР°РЅ BOT_TOKEN. Р”РѕР±Р°РІСЊ СЃРµРєСЂРµС‚ BOT_TOKEN РІ GitHub Actions."
        )

    if not CHANNEL:
        raise RuntimeError(
            "РќРµ Р·Р°РґР°РЅ CHANNEL."
        )

    print("==========================================")
    print("РњР Рљ [Р‘РР—РќР•РЎ РќРћР’РћРЎРўР] вЂ” Р·Р°РїСѓСЃРє")
    print("РўРµРјС‹: Р±РёР·РЅРµСЃ / СЌРєРѕРЅРѕРјРёРєР° / РїСЂРµРґРїСЂРёРЅРёРјР°С‚РµР»СЊСЃС‚РІРѕ / С‚РµС…РЅРѕР»РѕРіРёРё")
    print("РСЃС‚РѕС‡РЅРёРєРё: СЂРѕСЃСЃРёР№СЃРєРёРµ")
    print("==========================================")

    posted = load_posted()

    articles = fetch_all_feeds()

    print(f"РџРѕСЃР»Рµ С„РёР»СЊС‚СЂР°: {len(articles)}")

    articles = remove_duplicates(articles)

    print(f"РџРѕСЃР»Рµ РґРµРґСѓРїР»РёРєР°С†РёРё: {len(articles)}")

    selected = select_articles(articles, posted)

    print(f"Рљ РїСѓР±Р»РёРєР°С†РёРё: {len(selected)}")

    if not selected:
        print("РќРѕРІС‹С… РїРѕРґС…РѕРґСЏС‰РёС… РЅРѕРІРѕСЃС‚РµР№ РЅРµС‚.")
        return

    for article in selected:
        post = build_post(article)

        if not quality_check(article, post):
            print("РџСЂРѕРїСѓСЃРє: РЅРµ РїСЂРѕС€С‘Р» quality check")
            continue

        title = clean_text(article.get("title", ""))
        link = normalize_link(article.get("link", ""))

        print("------------------------------------------")
        print(title)
        print(article.get("source", ""))
        print(link)

        try:
            # РР·РѕР±СЂР°Р¶РµРЅРёРµ РЅРµРѕР±СЏР·Р°С‚РµР»СЊРЅРѕ.
            # Р•СЃР»Рё РЅР°Р№С‚Рё РЅРµ СѓРґР°Р»РѕСЃСЊ вЂ” РѕС‚РїСЂР°РІР»СЏРµРј РѕР±С‹С‡РЅС‹Р№ РїРѕСЃС‚.
            image = find_image(link)

            if image:
                send_photo(image, post)
                print("РћРїСѓР±Р»РёРєРѕРІР°РЅРѕ СЃ РёР·РѕР±СЂР°Р¶РµРЅРёРµРј.")
            else:
                send_message(post)
                print("РћРїСѓР±Р»РёРєРѕРІР°РЅРѕ Р±РµР· РёР·РѕР±СЂР°Р¶РµРЅРёСЏ.")

            posted.append(article_key(article))
            save_posted(posted)

        except Exception as e:
            print(f"РћС€РёР±РєР° РїСѓР±Р»РёРєР°С†РёРё: {e}")

    print("Р“РѕС‚РѕРІРѕ.")


if __name__ == "__main__":
    main()
