import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

import requests
from openpyxl import Workbook, load_workbook
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_OWNER = os.getenv("CARD_OWNER", "")

# Railway volume bo'lmasa ham ishlaydi
BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "data"
CHECKS_DIR = BASE_DIR / "checks"
DB_PATH = DATA_DIR / "bot.db"
EXCEL_PATH = DATA_DIR / "payments.xlsx"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHECKS_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# STEPS
# =========================
STEP_ID = "step_id"
STEP_NAME = "step_name"
STEP_AMOUNT = "step_amount"
STEP_WAIT_PROOF = "step_wait_proof"

# =========================
# TEXTS
# =========================
START_TEXT = (
    "👋 Ассалому алайкум!\n\n"
    "🤖 Мен ХЖ тўлов ёрдамчи ботиман.\n\n"
    "Ушбу бот орқали сиз аккаунтингизни тўлдириш учун сўров юборишингиз мумкин.\n\n"
    "📌 Жараённи бошлаш учун қуйидаги тугмани босинг."
)

ASK_ID_TEXT = (
    "🆔 1-қадам: ID рақамингизни киритинг\n\n"
    "Илтимос, 7 хонали ID рақам киритинг.\n\n"
    "Масалан:\n"
    "0012345"
)

ASK_NAME_TEXT = (
    "👤 2-қадам: Исм ва фамилиянгизни киритинг\n\n"
    "Илтимос, аккаунтингиздаги исм ва фамилиянгизни тўлиқ киритинг.\n\n"
    "Масалан:\n"
    "Алиев Алишер"
)

ASK_AMOUNT_TEXT = (
    "💵 3-қадам: Тўлдириш суммасини киритинг\n\n"
    "Илтимос, тўлдирмоқчи бўлган суммани АҚШ долларида киритинг.\n\n"
    "Масалан:\n"
    "10"
)

OFFER_TEXT = (
    "📜 Оммавий оферта шартлари\n\n"
    "Ушбу хизмат орқали амалга оширилган тўловлар фақат аккаунтни тўлдириш мақсадида қабул қилинади.\n\n"
    "⚠️ Фойдаланувчи томонидан киритилган ID рақам ва маълумотлар тўғри бўлиши шарт.\n\n"
    "💳 Тўлов администратор томонидан текширилгандан кейин қабул қилинади.\n\n"
    "⏳ Тўлов тасдиқлангандан кейин маблағ 24 соат ичида аккаунтингизга туширилади."
)

# =========================
# HELPERS
# =========================
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʼ'`-]+$")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fmt_uzs(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def decimal_to_plain_str(value: Decimal) -> str:
    # 20 -> "20", 10.5 -> "10.5", 2E+1 emas
    return format(value.normalize(), "f").rstrip("0").rstrip(".") if "." in format(value.normalize(), "f") else format(value.normalize(), "f")


def parse_decimal(text: str) -> Optional[Decimal]:
    cleaned = text.strip().replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None

    if value <= 0:
        return None

    return value


def validate_full_name(text: str) -> bool:
    parts = text.split()
    if len(parts) < 2:
        return False

    for part in parts:
        if len(part) < 2:
            return False
        if not NAME_RE.match(part):
            return False

    return True


def get_usd_rate() -> Decimal:
    # CBU XML endpoint
    url = "https://cbu.uz/ru/arkhiv-kursov-valyut/xml/USD/"
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    rate_text = root.findtext(".//Rate")
    if not rate_text:
        raise ValueError("Kurs topilmadi")

    return Decimal(rate_text.replace(",", "."))


# =========================
# DB
# =========================
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            account_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            amount_usd TEXT NOT NULL,
            rate_uzs TEXT NOT NULL,
            amount_uzs TEXT NOT NULL,
            proof_path TEXT,
            proof_file_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            approved_at TEXT,
            completed_at TEXT,
            rejected_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def create_payment(
    *,
    user_id: int,
    username: str,
    account_id: str,
    full_name: str,
    amount_usd: str,
    rate_uzs: str,
    amount_uzs: str,
    proof_path: str,
    proof_file_id: str,
) -> int:
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO payments (
            user_id, username, account_id, full_name,
            amount_usd, rate_uzs, amount_uzs,
            proof_path, proof_file_id, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            user_id,
            username,
            account_id,
            full_name,
            amount_usd,
            rate_uzs,
            amount_uzs,
            proof_path,
            proof_file_id,
            now_str(),
        ),
    )

    payment_id = cur.lastrowid
    conn.commit()
    conn.close()
    return payment_id


def get_payment(payment_id: int) -> Optional[sqlite3.Row]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_payment_status(payment_id: int, status: str) -> Optional[sqlite3.Row]:
    conn = get_db()
    cur = conn.cursor()

    row = get_payment(payment_id)
    if row is None:
        conn.close()
        return None

    approved_at = row["approved_at"]
    completed_at = row["completed_at"]
    rejected_at = row["rejected_at"]

    if status == "approved":
        approved_at = now_str()
    elif status == "completed":
        completed_at = now_str()
    elif status == "rejected":
        rejected_at = now_str()

    cur.execute(
        """
        UPDATE payments
        SET status = ?, approved_at = ?, completed_at = ?, rejected_at = ?
        WHERE id = ?
        """,
        (status, approved_at, completed_at, rejected_at, payment_id),
    )
    conn.commit()
    conn.close()

    return get_payment(payment_id)


# =========================
# EXCEL
# =========================
def init_excel() -> None:
    if EXCEL_PATH.exists():
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Payments"

    ws.append(
        [
            "payment_id",
            "created_at",
            "user_id",
            "username",
            "account_id",
            "full_name",
            "amount_usd",
            "rate_uzs",
            "amount_uzs",
            "proof_path",
            "proof_file_id",
            "status",
            "approved_at",
            "completed_at",
            "rejected_at",
        ]
    )

    wb.save(EXCEL_PATH)


def append_excel_row(payment: sqlite3.Row) -> None:
    init_excel()
    wb = load_workbook(EXCEL_PATH)
    ws = wb.active

    # amount_usd va amount_uzs ni string qilib yozamiz -> 2E+1 bo'lmaydi
    ws.append(
        [
            str(payment["id"]),
            payment["created_at"],
            str(payment["user_id"]),
            payment["username"] or "",
            payment["account_id"],
            payment["full_name"],
            str(payment["amount_usd"]),
            str(payment["rate_uzs"]),
            str(payment["amount_uzs"]),
            payment["proof_path"] or "",
            payment["proof_file_id"] or "",
            payment["status"],
            payment["approved_at"] or "",
            payment["completed_at"] or "",
            payment["rejected_at"] or "",
        ]
    )

    wb.save(EXCEL_PATH)


def rewrite_excel() -> None:
    # status o'zgarganda excel to'liq qayta yoziladi
    init_excel()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payments ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Payments"

    ws.append(
        [
            "payment_id",
            "created_at",
            "user_id",
            "username",
            "account_id",
            "full_name",
            "amount_usd",
            "rate_uzs",
            "amount_uzs",
            "proof_path",
            "proof_file_id",
            "status",
            "approved_at",
            "completed_at",
            "rejected_at",
        ]
    )

    for row in rows:
        ws.append(
            [
                str(row["id"]),
                row["created_at"],
                str(row["user_id"]),
                row["username"] or "",
                row["account_id"],
                row["full_name"],
                str(row["amount_usd"]),
                str(row["rate_uzs"]),
                str(row["amount_uzs"]),
                row["proof_path"] or "",
                row["proof_file_id"] or "",
                row["status"],
                row["approved_at"] or "",
                row["completed_at"] or "",
                row["rejected_at"] or "",
            ]
        )

    wb.save(EXCEL_PATH)


# =========================
# KEYBOARDS
# =========================
def start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🚀 Давом этиш"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def restart_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🔄 Яна тўлдириш"]],
        resize_keyboard=True,
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Тасдиқлаш", callback_data="user_confirm"),
                InlineKeyboardButton("✏️ Ўзгартириш", callback_data="user_restart"),
            ]
        ]
    )


def offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Шартларга розиман", callback_data="offer_accept"),
                InlineKeyboardButton("❌ Бекор қилиш", callback_data="offer_cancel"),
            ]
        ]
    )


def admin_pending_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Тасдиқлаш", callback_data=f"admin_approve:{payment_id}"),
                InlineKeyboardButton("❌ Рад этиш", callback_data=f"admin_reject:{payment_id}"),
            ]
        ]
    )


def admin_approved_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💸 Пул тушди", callback_data=f"admin_complete:{payment_id}")]]
    )


# =========================
# TEXT BUILDERS
# =========================
def build_summary_text(account_id: str, full_name: str, amount_usd: str, rate_uzs: str, amount_uzs: str) -> str:
    return (
        "📋 Илтимос, маълумотларни текширинг\n\n"
        f"🆔 ID рақам: {account_id}\n"
        f"👤 Исм-фамилия: {full_name}\n"
        f"💵 Сумма: {amount_usd} USD\n"
        f"💱 Курс: {rate_uzs} сўм\n"
        f"💰 Жами: {amount_uzs} сўм\n\n"
        "Агар маълумотлар тўғри бўлса, тасдиқлаш тугмасини босинг."
    )


def build_payment_text(amount_uzs: str) -> str:
    return (
        "💳 Тўлов учун маълумот\n\n"
        "Қуйидаги карта рақамига тўловни амалга оширинг.\n\n"
        f"💳 Карта:\n{CARD_NUMBER}\n\n"
        f"👤 Қабул қилувчи:\n{CARD_OWNER}\n\n"
        f"💰 Тўлов суммаси:\n{amount_uzs} сўм\n\n"
        "📸 Тўловдан кейин чек расмини юборинг."
    )


def build_admin_caption(payment: sqlite3.Row) -> str:
    username = f"@{payment['username']}" if payment["username"] else "—"
    return (
        "📥 Янги тўлов сўрови\n\n"
        f"🗂 Сўров ID: {payment['id']}\n"
        f"🆔 ID рақам: {payment['account_id']}\n"
        f"👤 Исм-фамилия: {payment['full_name']}\n"
        f"💵 Сумма: {payment['amount_usd']} USD\n"
        f"💱 Курс: {payment['rate_uzs']} сўм\n"
        f"💰 Жами: {payment['amount_uzs']} сўм\n"
        f"👤 Telegram: {username}\n"
        f"🔢 User ID: {payment['user_id']}\n"
        f"🕒 Вақт: {payment['created_at']}"
    )


# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text(START_TEXT, reply_markup=start_keyboard())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text(
            "❌ Жараён бекор қилинди.\n\nҚайта бошлаш учун /start ни босинг.",
            reply_markup=ReplyKeyboardRemove(),
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    step = context.user_data.get("step")

    if user_text in ["🚀 Давом этиш", "🔄 Яна тўлдириш"]:
        context.user_data.clear()
        context.user_data["step"] = STEP_ID
        await update.message.reply_text(ASK_ID_TEXT, reply_markup=ReplyKeyboardRemove())
        return

    if step == STEP_ID:
        if not user_text.isdigit() or len(user_text) != 7:
            await update.message.reply_text(
                "❌ ID рақам нотўғри киритилди.\n\n"
                "Илтимос, 7 хонали ID рақам киритинг.\n\n"
                "Масалан:\n0012345"
            )
            return

        context.user_data["account_id"] = user_text
        context.user_data["step"] = STEP_NAME
        await update.message.reply_text(ASK_NAME_TEXT)
        return

    if step == STEP_NAME:
        if not validate_full_name(user_text):
            await update.message.reply_text(
                "❌ Исм ва фамилия нотўғри киритилди.\n\n"
                "Илтимос, тўлиқ ва тўғри киритинг.\n\n"
                "Масалан:\nАлиев Алишер"
            )
            return

        context.user_data["full_name"] = user_text
        context.user_data["step"] = STEP_AMOUNT
        await update.message.reply_text(ASK_AMOUNT_TEXT)
        return

    if step == STEP_AMOUNT:
        amount_decimal = parse_decimal(user_text)
        if amount_decimal is None:
            await update.message.reply_text(
                "❌ Сумма нотўғри киритилди.\n\n"
                "Илтимос, суммани рақам билан киритинг.\n\n"
                "Масалан:\n10"
            )
            return

        try:
            rate_decimal = get_usd_rate()
        except Exception as e:
            logger.exception("Kurs olishda xato: %s", e)
            await update.message.reply_text(
                "❌ Ҳозирча курсни олиб бўлмади.\n\n"
                "Бироздан кейин қайта уриниб кўринг."
            )
            return

        amount_uzs_int = int((amount_decimal * rate_decimal).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        amount_usd_str = decimal_to_plain_str(amount_decimal)
        rate_str = decimal_to_plain_str(rate_decimal)
        amount_uzs_str = fmt_uzs(amount_uzs_int)

        context.user_data["amount_usd"] = amount_usd_str
        context.user_data["rate_uzs"] = rate_str
        context.user_data["amount_uzs"] = amount_uzs_str

        await update.message.reply_text(
            build_summary_text(
                context.user_data["account_id"],
                context.user_data["full_name"],
                amount_usd_str,
                rate_str,
                amount_uzs_str,
            ),
            reply_markup=confirm_keyboard(),
        )
        return

    if step == STEP_WAIT_PROOF:
        await update.message.reply_text("📸 Илтимос, чекни фото кўринишида юборинг.")
        return

    await update.message.reply_text("ℹ️ Жараённи бошлаш учун /start ни босинг.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return

    if context.user_data.get("step") != STEP_WAIT_PROOF:
        await update.message.reply_text("ℹ️ Аввал /start орқали жараённи бошланг.")
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id

    file = await context.bot.get_file(file_id)
    filename = f"{uuid.uuid4().hex}.jpg"
    file_path = CHECKS_DIR / filename
    await file.download_to_drive(str(file_path))

    payment_id = create_payment(
        user_id=update.effective_user.id,
        username=update.effective_user.username or "",
        account_id=context.user_data["account_id"],
        full_name=context.user_data["full_name"],
        amount_usd=context.user_data["amount_usd"],
        rate_uzs=context.user_data["rate_uzs"],
        amount_uzs=context.user_data["amount_uzs"],
        proof_path=str(file_path),
        proof_file_id=file_id,
    )

    payment = get_payment(payment_id)
    if payment is None:
        await update.message.reply_text("❌ Сақлашда хато юз берди.")
        return

    append_excel_row(payment)

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=build_admin_caption(payment),
        reply_markup=admin_pending_keyboard(payment_id),
    )

    await update.message.reply_text(
        "✅ Сўровингиз қабул қилинди\n\n"
        "📤 Маълумотлар администраторга юборилди.\n\n"
        "⏳ Тўлов текширилгандан кейин сизга хабар берилади.",
        reply_markup=restart_keyboard(),
    )

    context.user_data.clear()


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    data = query.data or ""

    # User callbacks
    if data == "user_restart":
        context.user_data.clear()
        context.user_data["step"] = STEP_ID
        await query.message.reply_text(ASK_ID_TEXT)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if data == "user_confirm":
        await query.message.reply_text(OFFER_TEXT, reply_markup=offer_keyboard())
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if data == "offer_cancel":
        context.user_data.clear()
        await query.message.reply_text(
            "❌ Жараён бекор қилинди.\n\nҚайта бошлаш учун /start ни босинг."
        )
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if data == "offer_accept":
        context.user_data["step"] = STEP_WAIT_PROOF
        await query.message.reply_text(
            build_payment_text(context.user_data["amount_uzs"])
        )
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Admin callbacks
    if not data.startswith("admin_"):
        return

    if query.from_user.id != ADMIN_ID:
        await query.answer("Сизда рухсат йўқ.", show_alert=True)
        return

    action, payment_id_str = data.split(":")
    payment_id = int(payment_id_str)

    payment = get_payment(payment_id)
    if payment is None:
        await query.answer("Сўров топилмади.", show_alert=True)
        return

    if action == "admin_approve":
        if payment["status"] != "pending":
            await query.answer("Бу сўров аллақачон кўриб чиқилган.", show_alert=True)
            return

        updated = update_payment_status(payment_id, "approved")
        rewrite_excel()

        if updated:
            try:
                await context.bot.send_message(
                    chat_id=updated["user_id"],
                    text=(
                        "✅ Тўловингиз тасдиқланди\n\n"
                        "⏳ Маблағ 24 соат ичида аккаунтингизга туширилади."
                    ),
                )
            except Exception:
                logger.exception("Userga approved xabari yuborilmadi")

        new_caption = (query.message.caption or "") + "\n\n✅ ТАСДИҚЛАНДИ"
        try:
            await query.edit_message_caption(
                caption=new_caption,
                reply_markup=admin_approved_keyboard(payment_id),
            )
        except Exception:
            await query.message.reply_text(
                "✅ ТАСДИҚЛАНДИ",
                reply_markup=admin_approved_keyboard(payment_id),
            )
        return

    if action == "admin_reject":
        if payment["status"] != "pending":
            await query.answer("Бу сўровни рад этиб бўлмайди.", show_alert=True)
            return

        updated = update_payment_status(payment_id, "rejected")
        rewrite_excel()

        if updated:
            try:
                await context.bot.send_message(
                    chat_id=updated["user_id"],
                    text=(
                        "❌ Тўлов сўровингиз рад этилди.\n\n"
                        "Илтимос, маълумотларни қайта текшириб юборинг."
                    ),
                )
            except Exception:
                logger.exception("Userga reject xabari yuborilmadi")

        new_caption = (query.message.caption or "") + "\n\n❌ РАД ЭТИЛДИ"
        try:
            await query.edit_message_caption(
                caption=new_caption,
                reply_markup=None,
            )
        except Exception:
            await query.message.reply_text("❌ РАД ЭТИЛДИ")
        return

    if action == "admin_complete":
        if payment["status"] != "approved":
            await query.answer("Аввал тасдиқлаш керак.", show_alert=True)
            return

        updated = update_payment_status(payment_id, "completed")
        rewrite_excel()

        if updated:
            try:
                await context.bot.send_message(
                    chat_id=updated["user_id"],
                    text=(
                        "🎉 Муваффақиятли!\n\n"
                        "💸 Пул аккаунтингизга туширилди.\n\n"
                        "Керак бўлса яна ботдан фойдаланишингиз мумкин."
                    ),
                    reply_markup=restart_keyboard(),
                )
            except Exception:
                logger.exception("Userga complete xabari yuborilmadi")

        new_caption = (query.message.caption or "") + "\n\n💸 ПУЛ ТУШДИ"
        try:
            await query.edit_message_caption(
                caption=new_caption,
                reply_markup=None,
            )
        except Exception:
            await query.message.reply_text("💸 ПУЛ ТУШДИ")
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Xatolik yuz berdi", exc_info=context.error)


def validate_env() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not ADMIN_ID:
        missing.append("ADMIN_ID")
    if not CARD_NUMBER:
        missing.append("CARD_NUMBER")
    if not CARD_OWNER:
        missing.append("CARD_OWNER")

    if missing:
        raise RuntimeError(f"Env topilmadi: {', '.join(missing)}")


def main() -> None:
    validate_env()
    init_db()
    init_excel()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi")
    app.run_polling()


if __name__ == "__main__":
    main()
