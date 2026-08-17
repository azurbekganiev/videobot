# videobot

Telegram-бот для скачивания видео/аудио с YouTube, Instagram и TikTok по ссылке.

## Возможности

- **YouTube** — выбор качества перед скачиванием: 1080p / 720p / 480p / аудио (MP3, 192kbps).
- **Instagram / TikTok** — скачивание сразу в лучшем доступном качестве, без выбора.
- Скачанный файл отправляется в чат и удаляется с диска.
- `/stats` (только для админа) — число пользователей и скачиваний с разбивкой по платформам.

## Стек

- [aiogram](https://github.com/aiogram/aiogram) — Telegram Bot API
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — загрузка видео
- SQLite — хранение пользователей и статистики
- Локальный [telegram-bot-api](https://github.com/tdlib/telegram-bot-api) сервер — снимает лимит в 50 МБ на отправку файлов ботом (до 2 ГБ)

## Запуск

1. Поднять локальный Telegram Bot API сервер (см. образ `aiogram/telegram-bot-api`), слушающий `127.0.0.1:8081`.
2. Установить зависимости:
   ```bash
   python -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
3. Скопировать `.env.example` в `.env` и заполнить:
   - `BOT_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
   - `ADMIN_ID` — Telegram user id администратора
   - `DB_PATH`, `COOKIE_PATH`, `DOWNLOADS_DIR` — пути на диске (по умолчанию рассчитаны на запуск из `/root/videobot`)
4. При необходимости положить `cookies.txt` (формат Netscape) рядом — используется yt-dlp для авторизованных запросов к YouTube/Instagram.
5. Запустить:
   ```bash
   set -a; source .env; set +a
   venv/bin/python bot.py
   ```

## Не в репозитории

`database.db`, `cookies.txt`, `downloads/`, `venv/`, `.env` — исключены через `.gitignore` (личные данные пользователей, сессионные куки, временные файлы).

## Важно

Загрузка видео с YouTube/Instagram/TikTok в обход их официальных API может нарушать условия использования этих платформ — используйте на свой риск.
