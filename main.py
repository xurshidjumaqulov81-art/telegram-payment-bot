import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
👋 Ассалому алайкум!

🤖 Мен ХЖ тўлов ёрдамчи ботиман.

Ушбу бот орқали сиз:
💰 аккаунтингизни тўлдириш учун сўров юборишингиз мумкин.

📌 Илтимос, жараённи бошлаш учун
қуйидаги тугмани босинг.
"""

    keyboard = [["▶️ Давом этиш"]]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(text, reply_markup=reply_markup)


# CONTINUE BUTTON
async def handle_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.text == "▶️ Давом этиш":

        text = """
🆔 1-қадам: ID рақамингизни киритинг

Илтимос, аккаунтингизга тегишли
ID рақамни киритинг.

⚠️ ID рақам 7 хонали бўлиши керак.

Масалан:
0012345
"""

        await update.message.reply_text(text)
        context.user_data["step"] = "id"


# ID INPUT
async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("step") == "id":

        user_id = update.message.text.strip()

        if not user_id.isdigit() or len(user_id) != 7:

            await update.message.reply_text(
                "❌ ID рақам нотўғри.\n\n"
                "Илтимос 7 хонали ID киритинг.\n"
                "Масалан: 0012345"
            )
            return

        context.user_data["account_id"] = user_id

        await update.message.reply_text(
            "✅ ID қабул қилинди.\n\n"
            "Кейинги қадамда исм фамилия киритилади."
        )


def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_continue))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_id))

    print("Bot ishga tushdi")

    app.run_polling()


if __name__ == "__main__":
    main()        "Масалан: 0012345"
    )

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_command))

    print("Bot ishga tushdi")

    app.run_polling()

if __name__ == "__main__":
    main()
