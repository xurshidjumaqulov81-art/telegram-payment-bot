import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    text = (
        "👋 Ассалому алайкум!\n\n"
        "🤖 Мен ХЖ тўлов ёрдамчи ботиман.\n\n"
        "Ушбу бот орқали сиз аккаунтингизни тўлдириш учун сўров юборишингиз мумкин.\n\n"
        "📌 Жараённи бошлаш учун қуйидаги тугмани босинг."
    )

    keyboard = [["🚀 Давом этиш"]]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(text, reply_markup=reply_markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    step = context.user_data.get("step")

    # Давом этиш тугмаси
    if user_text == "🚀 Давом этиш":
        context.user_data["step"] = "id"
        await update.message.reply_text(
            "🆔 1-қадам: ID рақамингизни киритинг\n\n"
            "Илтимос, 7 хонали ID рақам киритинг.\n\n"
            "Масалан:\n"
            "0012345",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # ID қадами
    if step == "id":
        if not user_text.isdigit() or len(user_text) != 7:
            await update.message.reply_text(
                "❌ ID рақам нотўғри киритилди.\n\n"
                "Илтимос, 7 хонали ID рақам киритинг.\n\n"
                "Масалан:\n"
                "0012345"
            )
            return

        context.user_data["account_id"] = user_text
        context.user_data["step"] = "full_name"

        await update.message.reply_text(
            "👤 2-қадам: Исм ва фамилиянгизни киритинг\n\n"
            "Илтимос, аккаунтингиздаги исм ва фамилиянгизни тўлиқ киритинг.\n\n"
            "Масалан:\n"
            "Алиев Алишер"
        )
        return

    # Исм фамилия қадами
    if step == "full_name":
        if len(user_text) < 5 or " " not in user_text:
            await update.message.reply_text(
                "❌ Исм ва фамилия нотўғри киритилди.\n\n"
                "Илтимос, тўлиқ киритинг.\n\n"
                "Масалан:\n"
                "Алиев Алишер"
            )
            return

        context.user_data["full_name"] = user_text
        context.user_data["step"] = "done"

        await update.message.reply_text(
            "✅ Маълумот қабул қилинди.\n\n"
            f"🆔 ID: {context.user_data['account_id']}\n"
            f"👤 Исм-фамилия: {context.user_data['full_name']}\n\n"
            "Кейинги қадамда сумма киритишни қўшамиз."
        )
        return


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
