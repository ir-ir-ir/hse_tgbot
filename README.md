# hse_tgbot

Telegram-бот для публикации новостей студентами с модерацией администраторов.

*Пайплайн:*
- Студент через бота заполняет пошаговую форму (заголовок, текст, фото, ссылки)
- Заявка отправляется всем администраторам с кнопками «Одобрить / Отклонить»
- При отклонении администратор указывает причину
- Одобренный материал автоматически публикуется в канал, студент получает уведомление

## Стек

- Python 3.11 + [aiogram 3.x](https://docs.aiogram.dev/) (async)
- SQLite через `aiosqlite` + SQLAlchemy 2.x (async) — хранение заявок
- Redis — внешнее хранилище для FSM (состояния не сбрасываются при перезапуске)
- `pydantic-settings` — конфигурация через `.env`

## Структура проекта

```
hse_tgbot/
├── src/
│   ├── bot.py                 # точка входа: dispatcher, bot, RedisStorage (FSM)
│   ├── config.py              # Settings + Redis (redis_url, fsm_ttl)
│   ├── database.py            # SQLAlchemy модели, engine, CRUD
│   ├── publisher.py           # публикация одобренного материала в канал
│   ├── filters/
│   │   └── admin.py           # AdminFilter
│   ├── handlers/
│   │   ├── student.py         # FSM-диалог /submit, /status
│   │   └── admin.py           # модерация, /pending, /history
│   ├── keyboards/
│   │   ├── student.py         # ReplyKeyboard «Пропустить / Готово / Отменить»
│   │   └── admin.py           # InlineKeyboard + CallbackData модерации
│   └── states/
│       └── submission.py      # StatesGroup для студента и модератора
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Настройка

1. Создайте бота у [@BotFather](https://t.me/BotFather), получите `BOT_TOKEN`.
2. Создайте канал, добавьте бота как администратора **с правом публиковать сообщения**.
3. Получите свой `user_id` (например, через [@userinfobot](https://t.me/userinfobot)) — добавьте в `ADMIN_IDS`.
4. Скопируйте `.env.example` в `.env` и заполните:

   ```env
   BOT_TOKEN=123456:ABC...
   ADMIN_IDS=[11111111,22222222]
   CHANNEL_ID=@mychannel        # или числовой -1001234567890
   DATABASE_URL=sqlite+aiosqlite:///submissions.db
   ```

## Запуск

### Локально

Установить Redis: https://github.com/microsoftarchive/redis/releases

1. Запустить командную строку от имени администратора
2. Перейти в папку, куда установился Redis 
3. Запустить
```bash
.\redis-server.exe redis.windows.conf
```
Запуск бота:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.bot
```

### Через Docker

```bash
docker compose up --build -d
docker compose logs -f bot
```

База данных SQLite будет создана автоматически.

## Команды

### Для студентов
- `/start` — приветствие
- `/submit` — подать новость (заголовок → текст → фото → ссылки → подтверждение)
- `/status` — посмотреть статусы своих заявок
- `/cancel` — прервать заполнение формы

### Для администраторов
- `/pending` — список заявок на модерации
- `/history` — последние 20 обработанных заявок
- Под каждой заявкой — кнопки `✅ Одобрить` / `❌ Отклонить`
  (после нажатия «Отклонить» бот попросит причину)

## Замечания

- Состояния FSM хранятся в `MemoryStorage` — при перезапуске незавершённые подачи
  сбрасываются. Сами заявки в БД сохраняются.
- В `.env` `CHANNEL_ID` может быть либо `@username` (публичный канал), либо
  числовым id вида `-100...` (приватный канал).
- Лимит фото в заявке — 10 (ограничение Telegram для media group).
- Лимит текста — 3000 символов.
