"""
Telegram-бот для збору пробігів водіїв
Дані зберігаються в Google Sheets
"""

import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
from sheets import save_mileage_record, get_car_list

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стани розмови
SELECT_CAR, ENTER_MILEAGE, SEND_PHOTO, CONFIRM = range(4)

BOT_TOKEN = os.environ["BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок — вибір автомобіля"""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.full_name}) started bot")

    cars = get_car_list()
    if not cars:
        await update.message.reply_text(
            "⚠️ Список автомобілів порожній. Зверніться до адміністратора."
        )
        return ConversationHandler.END

    # Формуємо клавіатуру з кнопками авто
    buttons = [[KeyboardButton(car)] for car in cars]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        f"👋 Привіт, {user.first_name}!\n\n"
        "🚗 *Оберіть свій автомобіль:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return SELECT_CAR


async def car_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Водій обрав авто — просимо пробіг"""
    selected = update.message.text
    cars = get_car_list()

    if selected not in cars:
        await update.message.reply_text("❌ Оберіть авто зі списку.")
        return SELECT_CAR

    context.user_data["car"] = selected
    await update.message.reply_text(
        f"✅ Обрано: *{selected}*\n\n"
        "📍 Введіть *поточний пробіг* (тільки цифри, наприклад: `245800`):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return ENTER_MILEAGE


async def mileage_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Водій ввів пробіг — просимо фото"""
    text = update.message.text.strip().replace(" ", "").replace(",", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Пробіг має містити лише цифри.\n"
            "Спробуйте ще раз (наприклад: `245800`):",
            parse_mode="Markdown"
        )
        return ENTER_MILEAGE

    mileage = int(text)
    if mileage < 1000 or mileage > 9999999:
        await update.message.reply_text(
            "❌ Схоже, пробіг введено неправильно. Перевірте і введіть знову:"
        )
        return ENTER_MILEAGE

    context.user_data["mileage"] = mileage
    await update.message.reply_text(
        f"✅ Пробіг: *{mileage:,} км*\n\n"
        "📸 Тепер надішліть *фото спідометра* для підтвердження:",
        parse_mode="Markdown"
    )
    return SEND_PHOTO


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримали фото — показуємо підтвердження"""
    photo = update.message.photo[-1]  # Найвища якість
    file_id = photo.file_id
    context.user_data["photo_file_id"] = file_id

    car = context.user_data["car"]
    mileage = context.user_data["mileage"]

    buttons = [
        [KeyboardButton("✅ Підтвердити"), KeyboardButton("❌ Скасувати")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "📋 *Перевірте дані перед збереженням:*\n\n"
        f"🚗 Авто: *{car}*\n"
        f"📍 Пробіг: *{mileage:,} км*\n"
        f"📅 Дата: *{datetime.now().strftime('%d.%m.%Y %H:%M')}*\n\n"
        "Все вірно?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Підтвердження — зберігаємо в Sheets"""
    answer = update.message.text

    if answer == "❌ Скасувати":
        await update.message.reply_text(
            "🚫 Скасовано. Напишіть /start щоб почати знову.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    if answer != "✅ Підтвердити":
        await update.message.reply_text("Оберіть одну з кнопок.")
        return CONFIRM

    user = update.effective_user
    car = context.user_data["car"]
    mileage = context.user_data["mileage"]
    photo_file_id = context.user_data["photo_file_id"]
    now = datetime.now()

    await update.message.reply_text("⏳ Зберігаємо...", reply_markup=ReplyKeyboardRemove())

    try:
        save_mileage_record(
            driver_name=user.full_name,
            driver_id=str(user.id),
            car=car,
            mileage=mileage,
            photo_file_id=photo_file_id,
            timestamp=now
        )
        await update.message.reply_text(
            "✅ *Збережено!*\n\n"
            f"🚗 {car}\n"
            f"📍 {mileage:,} км\n"
            f"📅 {now.strftime('%d.%m.%Y %H:%M')}\n\n"
            "Дякуємо! 👍",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error saving record: {e}")
        await update.message.reply_text(
            "❌ Помилка при збереженні. Зверніться до адміністратора."
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 Скасовано. Напишіть /start щоб почати знову.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, car_selected)],
            ENTER_MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mileage_entered)],
            SEND_PHOTO: [MessageHandler(filters.PHOTO, photo_received)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_error_handler(error_handler)

    logger.info("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
