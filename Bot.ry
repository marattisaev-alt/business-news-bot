import os
import requests

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

text = "📰 Бизнес-бот запущен!\n\nЭто тестовая публикация."

response = requests.post(
    url,
    data={
        "chat_id": CHANNEL,
        "text": text
    }
)

print(response.text)
