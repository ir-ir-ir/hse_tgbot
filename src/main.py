import os                                             # для чтения переменных окружения
from dotenv import load_dotenv                        # чтобы загрузить токен из файла .env
from telegram import Update                           # объект, который содержит всю информацию о пришедшем сообщении
from telegram.ext import Application, CommandHandler  # движок бота и обработчик комманд

load_dotenv()                                         # загрузка токена из файла .env

# Обработчик команды /start
async def start(update: Update, context):
    """Приветствие при запуске бота"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!👋\n\n"
        f"Отправь команду /news, чтобы предложить новость."
    )

# Обработчик команды /help
async def help_command(update: Update, context):
    """Справка по командам"""
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start - приветствие\n"
        "/news - предложить новость (скоро заработает)\n"
        "/help - эта справка"
    )

# Обработчик команды /news
async def news_command(update: Update, context):
    """
    Команда для предложения новости.
    пока просто заглушка
    """
    await update.message.reply_text(
        "📰 Функция «Предложить новость» находится в разработке.\n"
        "Скоро она заработает! Следите за обновлениями:)"
    )

# Главная функция запуска бота
def main():
    """Запускаем бота"""

    # Берём токен из переменной окружения BOT_TOKEN
    token = os.getenv("BOT_TOKEN")

    # Если токен не задан – выдаём ошибку
    if not token:
        print("Ошибка: не найден BOT_TOKEN. Создайте файл .env и запишите туда BOT_TOKEN=ваш_токен")
        return

    # Создаём приложение
    app = Application.builder().token(token).build()

    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("news", news_command))

    # Запускаем бота (начинаем получать сообщения от Telegram)
    print("Бот запущен. Напишите ему /start")
    app.run_polling()

# Точка входа
if __name__ == "__main__":
    main()
