import os
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "")  # comma-separated Telegram user IDs
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip()]

MASTER_FILE_PATH = "master.xlsx"          # path to the master Excel file on disk
UPLOAD_DIR = "uploads"
CELL_ID_COLUMN = "Cell id"                # exact column name in your Excel file

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── States ────────────────────────────────────────────────────────────────────
CHOOSING_MODE = 1
WAITING_FOR_UPLOAD = 2
WAITING_FOR_CELL_ID = 3
WAITING_FOR_MASTER_UPLOAD = 4

# ── Per-session store: chat_id → {"df": DataFrame, "mode": "master"|"upload"} ─
sessions: dict[int, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def load_excel(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=str)
    df.columns = df.columns.str.strip()
    df[CELL_ID_COLUMN] = df[CELL_ID_COLUMN].str.strip()
    return df


def format_row(row: pd.Series, cell_id: str, index: int, total: int) -> str:
    header = f"📋 *Result {index}/{total} — Cell ID: `{cell_id}`*\n"
    lines = [header]
    for col, val in row.items():
        if pd.isna(val) or str(val).strip() in ("", "nan", "NaT", "None"):
            val = "—"
        lines.append(f"• *{col}*: `{val}`")
    return "\n".join(lines)


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Use Master File", callback_data="mode_master")],
        [InlineKeyboardButton("📤 Upload My Own File", callback_data="mode_upload")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")],
    ])


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    master_exists = os.path.exists(MASTER_FILE_PATH)
    master_status = "✅ Available" if master_exists else "❌ Not uploaded yet"

    text = (
        "👋 *Welcome to the Excel Lookup Bot!*\n\n"
        f"📁 *Master File:* {master_status}\n\n"
        "Choose how you'd like to search:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return CHOOSING_MODE


# ── Main menu via callback ────────────────────────────────────────────────────
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    master_exists = os.path.exists(MASTER_FILE_PATH)
    master_status = "✅ Available" if master_exists else "❌ Not uploaded yet"
    text = (
        "👋 *Welcome to the Excel Lookup Bot!*\n\n"
        f"📁 *Master File:* {master_status}\n\n"
        "Choose how you'd like to search:"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return CHOOSING_MODE


# ── Mode: Master File ─────────────────────────────────────────────────────────
async def mode_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not os.path.exists(MASTER_FILE_PATH):
        await query.edit_message_text(
            "❌ No master file has been uploaded yet.\n\n"
            "Ask an admin to upload the master file using /uploadmaster.",
            reply_markup=back_keyboard(),
        )
        return CHOOSING_MODE

    try:
        df = load_excel(MASTER_FILE_PATH)
    except Exception as e:
        await query.edit_message_text(
            f"❌ Failed to load master file:\n`{e}`",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )
        return CHOOSING_MODE

    if CELL_ID_COLUMN not in df.columns:
        await query.edit_message_text(
            f"❌ Master file is missing the `{CELL_ID_COLUMN}` column.\n"
            "Please ask an admin to upload a corrected file.",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )
        return CHOOSING_MODE

    sessions[query.from_user.id] = {"df": df, "mode": "master"}
    await query.edit_message_text(
        f"✅ *Master file loaded!* ({len(df)} rows)\n\n"
        "Send me a *Cell ID* (e.g. `LKI0`, `LKI09`) to look up a row.\n\n"
        "Type /menu to go back or /reload to refresh the master file.",
        parse_mode="Markdown",
    )
    return WAITING_FOR_CELL_ID


# ── Mode: Upload own file ─────────────────────────────────────────────────────
async def mode_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📤 Please upload your Excel file (`.xlsx` or `.xls`).",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )
    return WAITING_FOR_UPLOAD


async def handle_user_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith((".xlsx", ".xls")):
        await update.message.reply_text(
            "❌ Please send a valid Excel file (`.xlsx` or `.xls`).",
            parse_mode="Markdown",
        )
        return WAITING_FOR_UPLOAD

    await update.message.reply_text("⏳ Processing your file…")

    file = await context.bot.get_file(doc.file_id)
    local_path = os.path.join(UPLOAD_DIR, f"{update.effective_user.id}_{doc.file_name}")
    await file.download_to_drive(local_path)

    try:
        df = load_excel(local_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Could not read the file:\n`{e}`", parse_mode="Markdown")
        return WAITING_FOR_UPLOAD

    if CELL_ID_COLUMN not in df.columns:
        cols = ", ".join(df.columns.tolist())
        await update.message.reply_text(
            f"❌ Column `{CELL_ID_COLUMN}` not found in your file.\n\n"
            f"Columns detected:\n`{cols}`\n\n"
            "Please fix the column name and re-upload.",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )
        return WAITING_FOR_UPLOAD

    sessions[update.effective_user.id] = {"df": df, "mode": "upload"}
    await update.message.reply_text(
        f"✅ *File loaded!* ({len(df)} rows)\n\n"
        "Send me a *Cell ID* (e.g. `LKI0`, `LKI09`) to look up a row.\n\n"
        "Type /menu to go back or upload a new file anytime.",
        parse_mode="Markdown",
    )
    return WAITING_FOR_CELL_ID


# ── Cell ID lookup ────────────────────────────────────────────────────────────
async def handle_cell_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cell_id = update.message.text.strip()

    session = sessions.get(user_id)
    if not session:
        await update.message.reply_text(
            "⚠️ No file loaded. Use /menu to choose a file source.",
            reply_markup=main_menu_keyboard(),
        )
        return CHOOSING_MODE

    # If using master, always reload from disk to get latest data
    if session["mode"] == "master":
        try:
            session["df"] = load_excel(MASTER_FILE_PATH)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to reload master file:\n`{e}`", parse_mode="Markdown")
            return WAITING_FOR_CELL_ID

    df = session["df"]
    matches = df[df[CELL_ID_COLUMN].str.upper() == cell_id.upper()]

    if matches.empty:
        await update.message.reply_text(
            f"🔍 No row found for Cell ID `{cell_id}`.\n"
            "Please check the ID and try again.",
            parse_mode="Markdown",
        )
        return WAITING_FOR_CELL_ID

    total = len(matches)
    for i, (_, row) in enumerate(matches.iterrows(), start=1):
        msg = format_row(row, cell_id, i, total)
        if len(msg) > 4000:
            # split into chunks
            chunks = [msg[j:j+4000] for j in range(0, len(msg), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")

    source = "🗂 Master file" if session["mode"] == "master" else "📤 Your uploaded file"
    await update.message.reply_text(
        f"_Source: {source}_\n\nSend another Cell ID or /menu to go back.",
        parse_mode="Markdown",
    )
    return WAITING_FOR_CELL_ID


# ── /menu shortcut ────────────────────────────────────────────────────────────
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    master_exists = os.path.exists(MASTER_FILE_PATH)
    master_status = "✅ Available" if master_exists else "❌ Not uploaded yet"
    text = (
        "🏠 *Main Menu*\n\n"
        f"📁 *Master File:* {master_status}\n\n"
        "Choose how you'd like to search:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return CHOOSING_MODE


# ── /reload — refresh master file in session ──────────────────────────────────
async def reload_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(MASTER_FILE_PATH):
        await update.message.reply_text("❌ No master file found on the server.")
        return WAITING_FOR_CELL_ID
    try:
        df = load_excel(MASTER_FILE_PATH)
        sessions[update.effective_user.id] = {"df": df, "mode": "master"}
        await update.message.reply_text(
            f"🔄 Master file reloaded! ({len(df)} rows)\nSend a Cell ID to search.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to reload:\n`{e}`", parse_mode="Markdown")
    return WAITING_FOR_CELL_ID


# ── /uploadmaster — admin only ────────────────────────────────────────────────
async def upload_master_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and not is_admin(user_id):
        await update.message.reply_text("🚫 You don't have permission to update the master file.")
        return

    await update.message.reply_text(
        "🔐 *Admin: Upload Master File*\n\n"
        "Send the new master Excel file now.\n"
        "⚠️ This will replace the current master file for all users.",
        parse_mode="Markdown",
    )
    return WAITING_FOR_MASTER_UPLOAD


async def handle_master_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_IDS and not is_admin(user_id):
        await update.message.reply_text("🚫 You don't have permission to update the master file.")
        return CHOOSING_MODE

    doc = update.message.document
    if not doc.file_name.lower().endswith((".xlsx", ".xls")):
        await update.message.reply_text("❌ Please send a valid `.xlsx` or `.xls` file.", parse_mode="Markdown")
        return WAITING_FOR_MASTER_UPLOAD

    await update.message.reply_text("⏳ Uploading and validating master file…")

    file = await context.bot.get_file(doc.file_id)
    temp_path = MASTER_FILE_PATH + ".tmp"
    await file.download_to_drive(temp_path)

    try:
        df = load_excel(temp_path)
    except Exception as e:
        os.remove(temp_path)
        await update.message.reply_text(f"❌ Could not read the file:\n`{e}`", parse_mode="Markdown")
        return WAITING_FOR_MASTER_UPLOAD

    if CELL_ID_COLUMN not in df.columns:
        os.remove(temp_path)
        cols = ", ".join(df.columns.tolist())
        await update.message.reply_text(
            f"❌ Missing `{CELL_ID_COLUMN}` column.\n\nColumns found:\n`{cols}`",
            parse_mode="Markdown",
        )
        return WAITING_FOR_MASTER_UPLOAD

    # Replace master file
    os.replace(temp_path, MASTER_FILE_PATH)

    await update.message.reply_text(
        f"✅ *Master file updated successfully!*\n"
        f"📊 {len(df)} rows loaded.\n\n"
        "All users will get the new data on their next search.",
        parse_mode="Markdown",
    )
    return CHOOSING_MODE


# ── /info — show current session info ────────────────────────────────────────
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    master_exists = os.path.exists(MASTER_FILE_PATH)

    lines = ["ℹ️ *Bot Info*\n"]
    lines.append(f"👤 Your ID: `{user_id}`")
    lines.append(f"🔐 Admin: {'Yes' if is_admin(user_id) else 'No'}")
    lines.append(f"📁 Master file: {'✅ Present' if master_exists else '❌ Missing'}")

    if session:
        mode = "🗂 Master file" if session["mode"] == "master" else "📤 Uploaded file"
        lines.append(f"📌 Active source: {mode}")
        lines.append(f"📊 Rows in session: {len(session['df'])}")
    else:
        lines.append("📌 Active source: None (use /menu to select)")

    if is_admin(user_id):
        lines.append("\n🔧 *Admin Commands:*")
        lines.append("`/uploadmaster` — Upload new master file")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Set the TELEGRAM_BOT_TOKEN environment variable.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MODE: [
                CallbackQueryHandler(mode_master, pattern="^mode_master$"),
                CallbackQueryHandler(mode_upload, pattern="^mode_upload$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
                CommandHandler("menu", menu),
                CommandHandler("info", info),
                CommandHandler("uploadmaster", upload_master_command),
            ],
            WAITING_FOR_UPLOAD: [
                MessageHandler(filters.Document.ALL, handle_user_upload),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
                CommandHandler("menu", menu),
            ],
            WAITING_FOR_CELL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cell_id),
                MessageHandler(filters.Document.ALL, handle_user_upload),  # re-upload
                CommandHandler("menu", menu),
                CommandHandler("reload", reload_master),
                CommandHandler("info", info),
                CommandHandler("uploadmaster", upload_master_command),
            ],
            WAITING_FOR_MASTER_UPLOAD: [
                MessageHandler(filters.Document.ALL, handle_master_upload),
                CommandHandler("menu", menu),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("menu", menu),
            CommandHandler("info", info),
        ],
        per_user=True,
        per_chat=False,
        per_message=False,
    )

    app.add_handler(conv)

    print("🤖 Bot is running…")
    async with app:
        await app.start()
        await app.updater.start_polling()
        print("✅ Polling started. Press Ctrl+C to stop.")
        await asyncio.Event().wait()  # run forever until Ctrl+C
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
