# jupiter-news

Очередь постов для Telegram-канала [@jupiteragency](https://t.me/jupiteragency).

- `queue.json` — посты пишет задача по расписанию в Claude Code (8:45 и 16:45 МСК).
- Скрипт `jupiter_news_bot.php` на хостинге jupiteragency.ru по cron (9:00 и 17:00 МСК) берёт самый старый неопубликованный пост и отправляет его в канал.

Формат записи в `queue.json` (новые добавляются в конец массива, хранится не больше 50 последних):

```json
{
  "id": "2026-10-05-короткий-slug",
  "created_at": "2026-10-05T08:45:00+03:00",
  "source": "Oborot.ru",
  "link": "https://...",
  "hashtags": "#wildberries #отзывы",
  "text": "Текст поста без markdown, эмодзи, хэштегов и ссылок, до 600 символов."
}
```

Чтобы снять пост до публикации, удалите его запись из `queue.json`.
