import asyncio
import json
import os
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from ombre_client import OmbreClient

BOT_TOKEN = os.environ['TG_BOT_TOKEN']
ALLOWED_CHAT_ID = os.environ.get('ALLOWED_CHAT_ID', '')
SESSIONS_FILE = Path('/data/sessions.json')
OMBRE = OmbreClient()


def load_sessions() -> dict:
    try:
        if SESSIONS_FILE.exists():
            return json.loads(SESSIONS_FILE.read_text())
    except Exception:
        pass
    return {}


def save_sessions(sessions: dict) -> None:
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(sessions, ensure_ascii=False))


async def claude_run(prompt: str, session_id: str | None) -> tuple[str, str | None]:
    cmd = ['claude', '-p', '--output-format', 'stream-json']
    if session_id:
        cmd += ['--resume', session_id]
    cmd.append(prompt)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd='/app'
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
    except asyncio.TimeoutError:
        proc.kill()
        return '(响应超时，请重试)', session_id

    new_sid = session_id
    result = ''
    for line in stdout.decode(errors='replace').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if data.get('type') == 'result':
                result = data.get('result', '')
                sid = data.get('session_id')
                if sid:
                    new_sid = sid
        except json.JSONDecodeError:
            pass

    return (result or stdout.decode(errors='replace').strip() or '(无回复)'), new_sid


def get_memory(query: str) -> str:
    data = OMBRE.breath(query, limit=5)
    memories = data.get('memories', [])
    if not memories:
        return ''
    return '\n'.join(m.get('content', '') for m in memories if m.get('content'))


def split_msg(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return

    text = (update.message.text or '').strip()
    if not text:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    sessions = load_sessions()
    session_id = sessions.get(chat_id)

    memory = get_memory(text)
    prompt = text
    if memory:
        prompt = f'[相关记忆]\n{memory}\n\n{text}'

    reply, new_sid = await claude_run(prompt, session_id)

    if new_sid and new_sid != session_id:
        sessions[chat_id] = new_sid
        save_sessions(sessions)

    for part in split_msg(reply):
        await update.message.reply_text(part)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return
    sessions = load_sessions()
    sessions.pop(chat_id, None)
    save_sessions(sessions)
    await update.message.reply_text('对话已重置 (´・ω・`)')


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('reset', cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
