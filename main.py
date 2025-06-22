import logging
import os
import json
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InputFile, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)

DATA_FILE = "data.json"
TRAININGS_FILE = "trainings.json"
TIMEZONE = ZoneInfo("Europe/Kiev")
REMINDER_HOUR = 8

DEFAULT_DATA = {
    "start_date_no_iqos": None,
    "expenses": {},
    "categories": []
}

MENU = ReplyKeyboardMarkup([
    [KeyboardButton("📅 Дни без стиков"), KeyboardButton("💪 Тренировка")],
    [KeyboardButton("💸 Ввести трату"), KeyboardButton("📊 Статистика")],
    [KeyboardButton("📁 Скачать данные"), KeyboardButton("🗑️ Обнулить траты"), KeyboardButton("✏️ Редактировать тренировку")]
], resize_keyboard=True)


def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DATA, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key, val in DEFAULT_DATA.items():
        if key not in data:
            data[key] = val
    return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_trainings():
    if not os.path.exists(TRAININGS_FILE):
        return {}
    with open(TRAININGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_trainings(trainings):
    with open(TRAININGS_FILE, "w", encoding="utf-8") as f:
        json.dump(trainings, f, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["start_date_no_iqos"]:
        tomorrow = (datetime.now(TIMEZONE) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        data["start_date_no_iqos"] = tomorrow.isoformat()
        save_data(data)
    await update.message.reply_text("Добро пожаловать! Я готов работать 💪", reply_markup=MENU)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if context.user_data.get("awaiting_expense"):
        await handle_expense(update, context)
        return

    if context.user_data.get("awaiting_reset"):
        await confirm_reset(update, context)
        return

    if context.user_data.get("awaiting_edit_command"):
        await apply_training_edit(update, context)
        return

    if context.user_data.get("editing"):
        await handle_edit_training(update, context)
        return

    # Основное меню
    if text == "📅 Дни без стиков":
        await show_no_iqos(update)

    elif text == "💪 Тренировка":
        await show_training(update)

    elif text == "💸 Ввести трату":
        await update.message.reply_text("Введи сумму и категорию (пример: `150 еда`)")
        context.user_data["awaiting_expense"] = True

    elif text == "📊 Статистика":
        await show_stats(update)

    elif text == "📁 Скачать данные":
        await update.message.reply_document(InputFile(DATA_FILE))

    elif text == "🗑️ Обнулить траты":
        context.user_data["awaiting_reset"] = True
        await update.message.reply_text("❗ Ты точно хочешь обнулить ВСЕ траты? Напиши `Да` или `Нет`")

    elif text == "✏️ Редактировать тренировку":
        context.user_data["editing"] = True
        await update.message.reply_text("Какой день хочешь редактировать? (спина, грудь, руки, ноги, функционал)", reply_markup=ReplyKeyboardRemove())

    else:
        await update.message.reply_text("Выбери команду из меню 👇", reply_markup=MENU)


async def show_no_iqos(update: Update):
    data = load_data()
    start = datetime.fromisoformat(data["start_date_no_iqos"])
    now = datetime.now(TIMEZONE)
    delta = now - start
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes = remainder // 60
    if delta.total_seconds() < 0:
        await update.message.reply_text("📅 Отсчет начнётся завтра с 00:00!")
    else:
        await update.message.reply_text(f"🔥 Ты уже {days} дней {hours} часов {minutes} минут без стиков!")


async def handle_edit_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trainings = load_trainings()
    day = update.message.text.strip().lower()
    context.user_data["editing"] = False

    if day not in trainings:
        await update.message.reply_text("❌ Такого дня нет в тренировках. Попробуй снова.", reply_markup=MENU)
        return

    context.user_data["edit_day"] = day
    reply = "📋 Текущие упражнения:\n"

    if day == "руки":
        reply += "\nПлечи:\n" + "\n".join(trainings[day].get("плечи", []))
        reply += "\n\nБицепс:\n" + "\n".join(trainings[day].get("бицепс", []))
        reply += "\n\nТрицепс:\n" + "\n".join(trainings[day].get("трицепс", []))
    elif day == "функционал":
        reply += trainings[day].get("комментарий", "Нет описания")
    elif day in ["спина", "грудь"]:
        variants = trainings[day].get("варианты", [])
        for i, v in enumerate(variants):
            reply += f"\nВариант {i+1}:\n" + "\n".join(v) + "\n"
    elif day == "ноги":
        reply += "\n".join(trainings[day].get("фиксировано", []))

    reply += (
        "\n\n✏️ Что хочешь сделать?\n"
        "- Напиши `добавить: Упражнение`\n"
        "- Или `удалить: часть текста`\n"
        "Для тренировок рук можно добавить конкретно:\n"
        "`добавить плечи: упражнение`\n"
        "`добавить бицепс: упражнение`\n"
        "`добавить трицепс: упражнение`"
    )
    context.user_data["awaiting_edit_command"] = True
    await update.message.reply_text(reply)


async def apply_training_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_edit_command"):
        return

    trainings = load_trainings()
    day = context.user_data.get("edit_day")
    msg = update.message.text.strip()

    if not day:
        await update.message.reply_text("Ошибка: день тренировки не выбран.", reply_markup=MENU)
        context.user_data["awaiting_edit_command"] = False
        return

    if msg.lower().startswith("добавить плечи:"):
        item = msg.split("добавить плечи:", 1)[1].strip()
        trainings["руки"]["плечи"].append(item)
        await update.message.reply_text("✅ Добавлено в плечи.", reply_markup=MENU)

    elif msg.lower().startswith("добавить бицепс:"):
        item = msg.split("добавить бицепс:", 1)[1].strip()
        trainings["руки"]["бицепс"].append(item)
        await update.message.reply_text("✅ Добавлено в бицепс.", reply_markup=MENU)

    elif msg.lower().startswith("добавить трицепс:"):
        item = msg.split("добавить трицепс:", 1)[1].strip()
        trainings["руки"]["трицепс"].append(item)
        await update.message.reply_text("✅ Добавлено в трицепс.", reply_markup=MENU)

    elif msg.lower().startswith("добавить:"):
        item = msg[9:].strip()
        if day == "функционал":
            trainings[day]["комментарий"] += f"\n{item}"
        elif day in ["спина", "грудь"]:
            if "варианты" in trainings[day] and trainings[day]["варианты"]:
                trainings[day]["варианты"][0].append(item)
        elif day == "ноги":
            trainings[day]["фиксировано"].append(item)
        elif day == "руки":
            await update.message.reply_text("Укажи, куда добавить: плечи, бицепс или трицепс. Пример:\nдобавить плечи: упражнение", reply_markup=MENU)
            return
        await update.message.reply_text("✅ Добавлено!", reply_markup=MENU)

    elif msg.lower().startswith("удалить:"):
        term = msg[8:].strip()
        found = False
        def remove_item(lst): return [x for x in lst if term not in x]

        if day == "функционал":
            old = trainings[day]["комментарий"]
            trainings[day]["комментарий"] = old.replace(term, "")
            found = old != trainings[day]["комментарий"]

        elif day in ["спина", "грудь"]:
            for i in range(len(trainings[day]["варианты"])):
                old = trainings[day]["варианты"][i]
                new = remove_item(old)
                if old != new:
                    trainings[day]["варианты"][i] = new
                    found = True

        elif day == "ноги":
            old = trainings[day]["фиксировано"]
            new = remove_item(old)
            trainings[day]["фиксировано"] = new
            found = old != new

        elif day == "руки":
            for key in ["плечи", "бицепс", "трицепс"]:
                old = trainings[day][key]
                new = remove_item(old)
                trainings[day][key] = new
                if old != new:
                    found = True

        if found:
            await update.message.reply_text("🗑️ Удалено.", reply_markup=MENU)
        else:
            await update.message.reply_text("❌ Не найдено для удаления.", reply_markup=MENU)

    else:
        await update.message.reply_text(
            "Неизвестная команда. Пример:\n"
            "добавить: Упражнение\n"
            "удалить: часть текста",
            reply_markup=MENU
        )

    save_trainings(trainings)
    context.user_data["awaiting_edit_command"] = False


async def show_training(update: Update):
    trainings = load_trainings()
    weekday = datetime.now(TIMEZONE).strftime("%A")
    weekday_ru = {
        "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
        "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
    }[weekday]

    if weekday_ru == "Понедельник":  # Спина
        options = trainings.get("спина", {}).get("варианты", [])
        if not options:
            await update.message.reply_text("Планы спины не найдены.")
            return
        variant = random.choice(options)
        msg = f"📅 Сегодня {weekday_ru} — Тренировка СПИНА (вариант):\n\n"
        msg += "\n".join(variant)

    elif weekday_ru == "Вторник":  # Грудь
        options = trainings.get("грудь", {}).get("варианты", [])
        if not options:
            await update.message.reply_text("Планы груди не найдены.")
            return
        variant = random.choice(options)
        msg = f"📅 Сегодня {weekday_ru} — Тренировка ГРУДЬ (вариант):\n\n"
        msg += "\n".join(variant)

    elif weekday_ru == "Среда":  # Функционал
        comment = trainings.get("функционал", {}).get("комментарий", "Тренировку подбирает тренер лично")
        msg = f"📅 Сегодня {weekday_ru} — ФУНКЦИОНАЛ\n\n{comment}"

    elif weekday_ru == "Четверг":  # Руки
        parts = trainings.get("руки", {})
        if not parts:
            await update.message.reply_text("Планы рук не найдены.")
            return
        shoulders = parts.get("плечи", [])
        biceps = parts.get("бицепс", [])
        triceps = parts.get("трицепс", [])

        if len(shoulders) < 3 or len(biceps) < 2 or len(triceps) < 2:
            await update.message.reply_text("Недостаточно упражнений в планах рук.")
            return

        chosen_shoulders = random.sample(shoulders, 3)
        chosen_biceps = random.sample(biceps, 2)
        chosen_triceps = random.sample(triceps, 2)

        msg = f"📅 Сегодня {weekday_ru} — Тренировка РУК\n\n"
        msg += "Плечи:\n" + "\n".join(chosen_shoulders) + "\n\n"
        msg += "Бицепс:\n" + "\n".join(chosen_biceps) + "\n\n"
        msg += "Трицепс:\n" + "\n".join(chosen_triceps)

    elif weekday_ru == "Пятница":  # Ноги
        legs = trainings.get("ноги", {}).get("фиксировано", [])
        if not legs:
            await update.message.reply_text("Планы ног не найдены.")
            return
        msg = f"📅 Сегодня {weekday_ru} — Тренировка НОГ\n\n"
        msg += "\n".join(legs)

    else:
        msg = "Сегодня день отдыха! 💤"

    await update.message.reply_text(msg)


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    text = update.message.text.strip()
    parts = text.split(maxsplit=1)

    try:
        amount = float(parts[0].replace(",", "."))
        category = parts[1].strip()
    except:
        await update.message.reply_text("❌ Формат: `150 еда`")
        return

    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    data["expenses"].setdefault(today, []).append({"category": category, "amount": amount})

    if category not in data["categories"]:
        data["categories"].append(category)

    save_data(data)
    total = sum(e["amount"] for e in data["expenses"][today])
    await update.message.reply_text(f"✅ Добавлено: {category} — {amount} грн\nИтого за сегодня: {total} грн", reply_markup=MENU)
    context.user_data["awaiting_expense"] = False


async def show_stats(update: Update):
    data = load_data()
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    today_exp = data["expenses"].get(today, [])
    total_today = sum(e["amount"] for e in today_exp)

    last7 = [(datetime.now(TIMEZONE) - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    weekly_total = 0
    cat_totals = {}

    for day in last7:
        for e in data["expenses"].get(day, []):
            weekly_total += e["amount"]
            cat_totals[e["category"]] = cat_totals.get(e["category"], 0) + e["amount"]

    stats = f"📊 Сегодня: {total_today:.2f} грн\n🗓️ За 7 дней: {weekly_total:.2f} грн\n\n🔍 По категориям:\n"
    for cat, amt in cat_totals.items():
        stats += f"• {cat}: {amt:.2f} грн\n"

    await update.message.reply_text(stats, reply_markup=MENU)


async def confirm_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.text.strip().lower()
    if reply == "да":
        data = load_data()
        data["expenses"] = {}
        save_data(data)
        await update.message.reply_text("🗑️ Все траты обнулены!", reply_markup=MENU)
    else:
        await update.message.reply_text("Отмена сброса.", reply_markup=MENU)
    context.user_data["awaiting_reset"] = False


def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("BOT_TOKEN не установлен в переменных среды.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_menu))

    app.run_polling()


if __name__ == "__main__":
    main()
