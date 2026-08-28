import json, os
from pathlib import Path
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ombre_client import OmbreClient

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
ALLOWED_CHAT_ID = os.environ.get('ALLOWED_CHAT_ID', '')
PROXY_URL = os.environ.get('CLAUDE_PROXY_URL', 'http://localhost:8792')
PROXY_TOKEN = os.environ.get('PROXY_AUTH_TOKEN', '')
OMBRE_ENABLED = os.environ.get('OMBRE_ENABLED', 'true').lower() == 'true'
HISTORY_FILE = Path('/data/history.json')
OMBRE = OmbreClient() if OMBRE_ENABLED else None

MAX_HISTORY = 100


def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_history(data: dict):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False))


async def claude_chat(messages: list) -> str:
    headers = {'Content-Type': 'application/json'}
    if PROXY_TOKEN:
        headers['Authorization'] = f'Bearer {PROXY_TOKEN}'

    body = {
        'model': 'claude-opus-4-5',
        'max_tokens': 8096,
        'messages': messages,
        'stream': False,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f'{PROXY_URL}/v1/messages', json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data['content'][0]['text']


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    history = load_history()
    messages = history.get(chat_id, [])

    content = user_text
    if OMBRE:
        try:
            memories = await OMBRE.breath(user_text, limit=5)
            if memories:
                mem_text = '\n'.join(f'- {m}' for m in memories)
                content = f'[相关记忆]\n{mem_text}\n\n{user_text}'
        except Exception:
            pass

    messages.append({'role': 'user', 'content': content})

    try:
        reply = await claude_chat(messages)
        messages.append({'role': 'assistant', 'content': reply})
        history[chat_id] = messages[-MAX_HISTORY:]
        save_history(history)

        paragraphs = [p.strip() for p in reply.split('\n\n') if p.strip()]
        for para in (paragraphs or [reply]):
            await update.message.reply_text(para)
    except Exception as e:
        await update.message.reply_text(f'出错了：{e}')


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    history = load_history()
    history.pop(chat_id, None)
    save_history(history)
    await update.message.reply_text("对话已重置 (´·ω·`)")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("嗨 (´·ω·`)")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('reset', cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()


if __name__ == '__main__':
    main()
