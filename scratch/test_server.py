import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
import uvicorn
from bot.handlers import router as bot_router

app = FastAPI()
bot = Bot(token="8962490919:AAFtXUpwmYe8SrtkLjvsDFTntz2El9ckPs0")
dp = Dispatcher()
dp.include_router(bot_router)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = types.Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"EXCEPTION IN WEBHOOK: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error"}
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
