import asyncio
import os
import uuid
import sqlite3
import glob
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

BOT_TOKEN = os.environ['BOT_TOKEN']
ADMIN_ID = int(os.environ['ADMIN_ID'])

session = AiohttpSession(api=TelegramAPIServer.from_base('http://localhost:8081'))
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

links_db = {}
DB_PATH = os.environ.get('DB_PATH', '/root/videobot/database.db')
COOKIE_PATH = os.environ.get('COOKIE_PATH', '/root/videobot/cookies.txt')
DOWNLOADS_DIR = os.environ.get('DOWNLOADS_DIR', '/root/videobot/downloads')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                          (user_id INTEGER PRIMARY KEY, username TEXT, joined_at TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS downloads
                          (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, quality TEXT, platform TEXT)''')
        conn.commit()

def log_user(user_id, username):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username, joined_at) VALUES (?, ?, ?)',
                       (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

def log_download(user_id, quality, platform="youtube"):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO downloads (user_id, quality, platform) VALUES (?, ?, ?)',
                       (user_id, quality, platform))
        conn.commit()

@dp.message(CommandStart())
async def start_command(message: types.Message):
    log_user(message.from_user.id, message.from_user.username)
    await message.answer("Привет! Отправь мне ссылку на YouTube, Instagram или TikTok! 🚀")

# --- ОБНОВЛЕННАЯ СТАТИСТИКА ---
@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Считаем пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # Считаем общие скачивания
        cursor.execute("SELECT COUNT(*) FROM downloads")
        total_downloads = cursor.fetchone()[0]

        # Считаем скачивания с группировкой по платформам
        cursor.execute("SELECT platform, COUNT(*) FROM downloads GROUP BY platform")
        platform_stats = cursor.fetchall()

    # Формируем красивый текст ответа
    text = (
        f"📊 **Статистика бота:**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"📥 Всего скачиваний: {total_downloads}\n\n"
        f"🔥 **Источники загрузок:**\n"
    )

    # Перебираем платформы и добавляем их в сообщение
    if not platform_stats:
        text += "Пока пусто 🤷‍♂️"
    else:
        for platform, count in platform_stats:
            # Делаем первую букву заглавной (youtube -> Youtube)
            text += f"▪️ {platform.capitalize()}: {count}\n"

    await message.answer(text, parse_mode="Markdown")
# ------------------------------

@dp.message()
async def handle_url(message: types.Message):
    url = message.text.lower()
    if "http" not in url:
        await message.answer("Пожалуйста, отправь корректную ссылку.")
        return

    if "instagram.com" in url or "tiktok.com" in url:
        await process_fast_download(message, message.text)
        return

    link_id = str(uuid.uuid4())[:8]
    links_db[link_id] = message.text

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 1080p", callback_data=f"dl_1080_{link_id}"),
         InlineKeyboardButton(text="🎬 720p", callback_data=f"dl_720_{link_id}")],
        [InlineKeyboardButton(text="🎬 480p", callback_data=f"dl_480_{link_id}"),
         InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data=f"dl_audio_{link_id}")]
    ])
    await message.answer("Выбери качество для скачивания:", reply_markup=keyboard)

async def process_fast_download(message: types.Message, url: str):
    status_msg = await message.answer("Распознал короткое видео. Скачиваю... ⏳")
    platform = "instagram" if "instagram.com" in url else "tiktok"

    ydl_opts_download = {
        'format': 'best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best',
        'outtmpl': f'{DOWNLOADS_DIR}/%(id)s.%(ext)s',
        'max_filesize': 2000000000,
        'quiet': True,
    }

    if os.path.exists(COOKIE_PATH):
        ydl_opts_download['cookiefile'] = COOKIE_PATH

    await execute_download(message.from_user.id, message.chat.id, status_msg, url, ydl_opts_download, platform, "best")

@dp.callback_query(F.data.startswith('dl_'))
async def process_download(callback: types.CallbackQuery):
    _, quality, link_id = callback.data.split('_')
    url = links_db.get(link_id)

    if not url:
        await callback.answer("Ссылка устарела.", show_alert=True)
        return

    await callback.message.edit_text("Скачиваю и обрабатываю... ⏳")

    if quality == "audio":
        ydl_format = 'bestaudio/best'
        postprocessors = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    else:
        ydl_format = f'bestvideo[vcodec^=avc1][height<={quality}]+bestaudio[ext=m4a]/bestvideo[ext=mp4][height<={quality}]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        postprocessors = []

    ydl_opts_download = {
        'format': ydl_format,
        'outtmpl': f'{DOWNLOADS_DIR}/%(id)s.%(ext)s',
        'max_filesize': 2000000000,
        'quiet': True,
        'merge_output_format': 'mp4',
        'postprocessors': postprocessors
    }

    await execute_download(callback.from_user.id, callback.message.chat.id, callback.message, url, ydl_opts_download, "youtube", quality)

async def execute_download(user_id, chat_id, status_msg, url, ydl_opts, platform, quality):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            download_info = ydl.extract_info(url, download=True)
            base_filename = ydl.prepare_filename(download_info).rsplit('.', 1)[0]
            filename = base_filename + ('.mp3' if quality == "audio" else '.mp4')
            width, height = download_info.get('width'), download_info.get('height')

        await status_msg.edit_text("Загружаю в Telegram... 📤")
        file = types.FSInputFile(filename)

        if quality == "audio":
            await bot.send_audio(chat_id=chat_id, audio=file)
        else:
            send_kwargs = {}
            if width: send_kwargs['width'] = int(width)
            if height: send_kwargs['height'] = int(height)
            await bot.send_video(chat_id=chat_id, video=file, supports_streaming=True, **send_kwargs)

        if os.path.exists(filename): os.remove(filename)
        log_download(user_id, quality, platform)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"Произошла ошибка при скачивании.")
        if 'base_filename' in locals():
            for file_to_delete in glob.glob(f"{base_filename}*"):
                try: os.remove(file_to_delete)
                except: pass

async def main():
    init_db()
    print("Бот запущен. Раздельная аналитика активирована.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
