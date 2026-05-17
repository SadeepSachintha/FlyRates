import requests

TOKEN = "8962490919:AAFtXUpwmYe8SrtkLjvsDFTntz2El9ckPs0"
CHAT_ID = "1234567"

help_text = (
    "📚 **FlyRates Bot Help** 📚\n\n"
    "Here are the commands you can use:\n\n"
    "**Basic Commands**\n"
    "`/start` - Get welcome message\n"
    "`/help` - Show this help menu\n\n"
    "**Rates & Updates**\n"
    "`/current <base> <target>` - Get the live rate\n"
    "`/subscribe <base> <target> [daily/hourly]` - Automate updates\n"
    "`/threshold <base> <target> <condition> <value>` - Get custom alerts (<, >, <=, >=)\n\n"
    "**Management**\n"
    "`/mysubs` - View all your active subscriptions and alerts\n"
    "`/unsubscribe <base> <target>` - Remove a subscription\n"
    "`/delthreshold <base> <target>` - Remove an alert\n\n"
    f"**Supported Currencies:** USD, GBP, EUR\n\n"
    "**Examples:**\n"
    "`/current USD EUR`\n"
    "`/subscribe USD EUR hourly`\n"
    "`/threshold USD EUR < 0.90`"
)

res = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": help_text,
        "parse_mode": "Markdown"
    }
)

print("Markdown result:")
print(res.json())
