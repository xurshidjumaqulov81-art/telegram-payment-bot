import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
Ассалому алайкум.

Бу бот сизга экстрен ҳолатларда,
яъни Payme системаси ишламай қолганида
ёки дам олиш кунларига тўғри келиб қолганда
ҳисобингизни тўлдириш учун хизмат қилади.

Салом, мен ХЖ ёрдамчингизман.
Сизга аккаунтингизни тўлдиришга ёрдам бераман.

Илтимос /id командасини босиб жараённи бошланг.
"""

    await update.message.reply_text(text)

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "1. ID рақамингизни киритинг.\n\n"
        "ID рақам 7 хонали бўлиши керак.\n"
        "Масалан: 0012345"
    )

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_command))

    print("Bot ishga tushdi")

    app.run_polling()

if __name__ == "__main__":
    main()
