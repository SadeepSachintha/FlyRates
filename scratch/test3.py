import requests
from core.config import settings

TOKEN = settings.bot_token
CHAT_ID = "1234567"

# Valid markdown
help_text_valid = "*bold*"

# Invalid markdown - unclosed asterisk
help_text_invalid = "*bold"

print("Valid:")
print(requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": help_text_valid, "parse_mode": "Markdown"}
).json())

print("Invalid:")
print(requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": help_text_invalid, "parse_mode": "Markdown"}
).json())
