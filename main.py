import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from upstash_redis import Redis
from transformers import pipeline

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# Инициализация
redis = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)
chatbot = pipeline(
    "text-generation", 
    model="microsoft/DialoGPT-small", 
    use_auth_token=HF_API_TOKEN
)

# Сохранение контекста
async def save_context(chat_id: int, text: str, is_bot: bool = False):
    key = f"chat:{chat_id}"
    message = f"Bot: {text}" if is_bot else f"User: {text}"
    redis.lpush(key, message)
    redis.ltrim(key, 0, 99)  # Храним 100 последних сообщений

# Генерация ответа
async def generate_response(chat_id: int) -> str:
    history = redis.lrange(f"chat:{chat_id}", 0, -1)
    context = "\n".join([msg.decode() for msg in reversed(history)])
    response = chatbot(context, max_length=200, temperature=0.9)[0]['generated_text']
    return response.split("Bot:")[-1].strip()

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_message = update.message.text

    await save_context(chat_id, user_message)
    response = await generate_response(chat_id)
    await save_context(chat_id, response, is_bot=True)

    await update.message.reply_text(response)

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
