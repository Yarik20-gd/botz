import logging
import os
import json
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

DATA_FILE = "data.json"
TIMEZONE = ZoneInfo("Europe/Kiev")
REMINDER_HOUR = 8  # 8 утра по Киеву

# Изначальные данные
DEFAULT_DATA = {
    "start_date_no_iqos": "2024-06-01",
    "expenses": {},  # "YYYY-MM-DD": [{"category": str, "amount": float}]
}

# Тренировочные планы
TRAINING_DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]

TRAINING_PLANS = {
    "спина": ["тяга верхнего блока", "гребля в тренажере", "гиперэкстензия"],
    "грудь": ["жим лежа", "разводка гантелей", "отжимания"],
    "руки": ["бицепс со штангой", "трицепс на блоке", "молотки"],
    "ноги": ["присед", "выпады", "разгибание ног"],
    "функционал": ["бурпи", "медбол", "плиометрика"]
}

WARMUP = ["5 минут кардио", "разминка суставов", "легкий круг с резинкой"]
CARDIO = ["10 мин эллипс", "10 мин бег", "5 мин скакалка"]

# Клавиатура меню
MENU_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("📅 Дни без стиков"), KeyboardButton("💪 Тренировка")],
    [KeyboardButton("💸 Ввести трату"), KeyboardButton("📊 Статистика")],
], resize_keyboard=True)

# Загрузка/сохранение данных
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DATA, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для тренировок и учета расходов. Выбирай команду в меню.",
        reply_markup=MENU_KEYBOARD
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "📅 Дни без стиков":
        data = load_data()
        start_date = datetime.fromisoformat(data["start_date_no_iqos"])
        delta = datetime.now(TIMEZONE) - start_date
        await update.message.reply_text(f"Ты уже {delta.days} дней без стиков 💪")

    elif text == "💪 Тренировка":
        await send_training(update, context)

    elif text == "💸 Ввести трату":
        await update.message.reply_text("Пиши в формате: сумма категория\nНапример: 150 еда")

        # Включаем режим ожидания трат
        context.user_data["awaiting_expense"] = True

    elif text == "📊 Статистика":
        await send_stats(update, context)

    else:
        # Если пользователь в режиме ввода трат, ловим сумму и категорию
        if context.user_data.get("awaiting_expense"):
            await handle_expense_input(update, context)
        else:
            await update.message.reply_text("Пожалуйста, выбери команду из меню.", reply_markup=MENU_KEYBOARD)


async def send_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.now(TIMEZONE).strftime("%A")
    weekday_ru = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }[weekday]

    if weekday_ru not in TRAINING_DAYS:
        await update.message.reply_text("Сегодня день отдыха 😴")
        return

    if weekday_ru == "Среда":
        workout_type = "функционал"
    else:
        workout_type = random.choice(["спина", "грудь", "руки", "ноги"])

    workout = random.sample(TRAINING_PLANS[workout_type], k=3)
    warmup = random.choice(WARMUP)
    cardio = random.choice(CARDIO)

    message = (
        f"Сегодня {weekday_ru} – день {workout_type.upper()} 💥\n"
        f"Разминка: {warmup}\n"
        f"Основная часть: " + ", ".join(workout) + "\n"
        f"Кардио: {cardio}"
    )
    await update.message.reply_text(message)


async def handle_expense_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("Неверный формат. Пиши: сумма категория\nНапример: 150 еда")
        return

    try:
        amount = float(parts[0].replace(",", "."))
        category = parts[1].strip()
    except Exception:
        await update.message.reply_text("Ошибка при распознавании суммы. Попробуй еще раз.")
        return

    data = load_data()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    if today_str not in data["expenses"]:
        data["expenses"][today_str] = []
    data["expenses"][today_str].append({"category": category, "amount": amount})
    save_data(data)

    total = sum(e["amount"] for e in data["expenses"][today_str])
    await update.message.reply_text(f"Добавлено: {category} - {amount} грн. Всего за сегодня: {total} грн.", reply_markup=MENU_KEYBOARD)
    context.user_data["awaiting_expense"] = False


async def send_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    # Статистика за сегодня
    today_expenses = data["expenses"].get(today_str, [])
    total_today = sum(e["amount"] for e in today_expenses)

    # Статистика за последние 7 дней
    week_total = 0
    week_categories = {}

    for i in range(7):
        day = (datetime.now(TIMEZONE) - timedelta(days=i)).strftime("%Y-%m-%d")
        day_exp = data["expenses"].get(day, [])
        week_total += sum(e["amount"] for e in day_exp)
        for e in day_exp:
            week_categories[e["category"]] = week_categories.get(e["category"], 0) + e["amount"]

    msg = f"📊 Статистика расходов:\n\nСегодня: {total_today:.2f} грн\n\nЗа 7 дней: {week_total:.2f} грн\n\nПо категориям:\n"
    for cat, val in week_categories.items():
        msg += f"- {cat}: {val:.2f} грн\n"

    await update.message.reply_text(msg, reply_markup=MENU_KEYBOARD)


# Ежедневное утреннее напоминание
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    weekday = datetime.now(TIMEZONE).strftime("%A")
    weekday_ru = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }[weekday]

    if weekday_ru not in TRAINING_DAYS:
        await context.bot.send_message(chat_id, "Сегодня день отдыха 😴")
        return

    if weekday_ru == "Среда":
        workout_type = "функционал"
    else:
        workout_type = random.choice(["спина", "грудь", "руки", "ноги"])

    message = f"Доброе утро! Сегодня {weekday_ru}. Тренировка: {workout_type.upper()} 💪"
    await context.bot.send_message(chat_id, message)


async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.job_queue.run_daily(daily_reminder, time=datetime.time(REMINDER_HOUR, 0, 0, tzinfo=TIMEZONE), chat_id=chat_id)
    await update.message.reply_text("Утренние напоминания включены! Буду писать в 8:00 по Киеву.", reply_markup=MENU_KEYBOARD)


def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: переменная окружения BOT_TOKEN не найдена!")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reminder_on", set_reminder))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_menu))

    # Запуск планировщика APScheduler для напоминаний при запуске не нужен, т.к. мы включаем напоминание командой /reminder_on

    app.run_polling()


if __name__ == "__main__":
    main()
