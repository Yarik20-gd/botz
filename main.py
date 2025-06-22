import logging
import os
import random
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Начальная дата отказа от стиков
START_DATE_NO_IQOS = datetime(2024, 6, 1)

# Дни тренировок
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

EXPENSES = {}

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для тренировок, учёта расходов и отслеживания дней без стиков.")


async def days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    delta = today - START_DATE_NO_IQOS
    await update.message.reply_text(f"Ты уже {delta.days} дней без стиков 💪")


async def training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.now().strftime("%A")
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


async def spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text("Формат: /spend сумма описание (например: /spend 150 еда)")
            return

        amount, *reason = text.split()
        amount = float(amount)
        reason = " ".join(reason)
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str not in EXPENSES:
            EXPENSES[today_str] = []
        EXPENSES[today_str].append((reason, amount))
        total = sum(x[1] for x in EXPENSES[today_str])
        await update.message.reply_text(f"Добавлено: {reason} - {amount} грн. Всего за день: {total} грн.")
    except Exception as e:
        await update.message.reply_text("Ошибка ввода. Используй: /spend 100 транспорт")


async def today_spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today_str = datetime.now().strftime("%Y-%m-%d")
    day_expenses = EXPENSES.get(today_str, [])
    if not day_expenses:
        await update.message.reply_text("Сегодня ещё не было трат.")
        return
    message = "\n".join([f"{r} - {a} грн" for r, a in day_expenses])
    total = sum(x[1] for x in day_expenses)
    await update.message.reply_text(f"Сегодняшние траты:\n{message}\nИтого: {total} грн")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("days", days))
    app.add_handler(CommandHandler("training", training))
    app.add_handler(CommandHandler("spend", spend))
    app.add_handler(CommandHandler("today", today_spend))

    app.run_polling()


if __name__ == "__main__":
    main()
