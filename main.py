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
        "Ушбу бот орқали сиз:\n"
        "💰 аккаунтингизни тўлдириш учун сўров юборишингиз мумкин.\n\n"
        "📌 Илтимос, жараённи бошлаш учун қуйидаги тугмани босинг."
    )

    keyboard = [["🚀 Давом этиш"]]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    step = context.user_data.get("step")

    if text == "👉 Давом этиш":
        context.user_data["step"] = "id"

        await update.message.reply_text(
            "🆔 1-қадам: ID рақамингизни киритинг\n\n"
            "Илтимос, аккаунтингизга тегишли ID рақамни киритинг.\n\n"
            "⚠️ ID рақам 7 хонали бўлиши керак.\n\n"
            "Масалан:\n"
            "0012345",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    if step == "id":
        if not text.isdigit() or len(text) != 7:
            await update.message.reply_text(
                "❌ ID рақам нотўғри киритилди.\n\n"
                "Илтимос, 7 хонали ID рақам киритинг.\n\n"
                "Масалан:\n"
                "0012345"
            )
            return

        context.user_data["account_id"] = text
        context.user_data["step"] = "full_name"

        await update.message.reply_text(
            "✅ ID рақам қабул қилинди.\n\n"
            "👤 2-қадам: Исм ва фамилиянгизни киритинг\n\n"
            "Илтимос, аккаунтингиздаги исм ва фамилиянгизни тўлиқ ёзинг.\n\n"
            "Масалан:\n"
            "Алиев Алишер"
        )
        return

    if step == "full_name":
        if len(text) < 5 or " " not in text:
            await update.message.reply_text(
                "❌ Исм ва фамилия нотўғри киритилди.\n\n"
                "Илтимос, исм ва фамилиянгизни тўлиқ киритинг.\n\n"
                "Масалан:\n"
                "Алиев Алишер"
            )
            return

        context.user_data["full_name"] = text
        context.user_data["step"] = "done"

        await update.message.reply_text(
            "✅ Исм ва фамилия қабул қилинди.\n\n"
            "Кейинги қадамда сумма киритишни қўшамиз."
        )
        return


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot ishga tushdi")
    app.run_polling()


if __name__ == "__main__":
    main()
