1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
# -*- coding: utf-8 -*-
"""
MRK | БЕЗ ФИЛЬТРОВ — autonomous entertainment Telegram bot.
Collects RSS items, deduplicates, scores, and publishes concise posts.
Only use feeds you are permitted to access and media you have rights to use.
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
