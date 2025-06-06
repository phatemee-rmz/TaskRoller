import json
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, CallbackQueryHandler, ChatMemberHandler

# --- Constants ---
# TOKEN خود را در اینجا قرار دهید
TOKEN = "7807331640:AAFFzccQRJlZMNlQvkrQRNmX_xZwFGKqd2A"
CONFIG_FILE = "config.json"
NAMES_FILE = "names.json"
HISTORY_FILE = "history.json"

# --- Config & File Handling ---
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"group_chat_id": None}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_names():
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["individuals"], data["groups"]

def load_cycle_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_cycle_history(names):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False, indent=2)

# --- Name Selection Logic (Unchanged) ---
def select_people():
    individuals, groups = load_names()
    cycle_history = load_cycle_history()
    all_possible_names = individuals + [name for group in groups for name in group]
    available_pool = [name for name in all_possible_names if name not in cycle_history]
    
    if not available_pool:
        print("DEBUG: Cycle complete! Resetting history and starting a new cycle.")
        cycle_history = []
        available_pool = all_possible_names[:]
    
    selected_for_this_week = []
    available_groups = [g for g in groups if all(member in available_pool for member in g)]
    random.shuffle(available_groups)
    
    for g in available_groups:
        if len(selected_for_this_week) + len(g) <= 5:
            selected_for_this_week.extend(g)
            for member in g:
                if member in available_pool:
                    available_pool.remove(member)

    available_individuals = [p for p in individuals if p in available_pool]
    random.shuffle(available_individuals)
    
    while len(selected_for_this_week) < 5 and available_individuals:
        person = available_individuals.pop(0)
        selected_for_this_week.append(person)
    
    if len(selected_for_this_week) < 5:
        print("DEBUG: Available pool depleted mid-selection. Resetting cycle to fill remaining spots.")
        needed = 5 - len(selected_for_this_week)
        cycle_history = selected_for_this_week[:]
        new_pool = [p for p in all_possible_names if p not in selected_for_this_week]
        random.shuffle(new_pool)
        selected_for_this_week.extend(new_pool[:needed])
    else:
        cycle_history.extend(selected_for_this_week)

    save_cycle_history(cycle_history)
    return selected_for_this_week

def build_keyboard(names, buttons_per_row=2):
    buttons = [InlineKeyboardButton(f"{name} غایبم!", callback_data=name) for name in names]
    keyboard = [buttons[i:i+buttons_per_row] for i in range(0, len(buttons), buttons_per_row)]
    return InlineKeyboardMarkup(keyboard)

# --- Core Bot Handlers ---
async def send_names(context: CallbackContext, chat_id_to_send: int):
    """این تابع لیست اسامی را به چت مشخص شده ارسال می‌کند"""
    if not chat_id_to_send:
        print("ERROR: Cannot send names. Chat ID is not provided.")
        return

    names = select_people()
    if not names:
        await context.bot.send_message(chat_id=chat_id_to_send, text="خطا: مشکلی در انتخاب اسامی پیش آمده است!")
        return
        
    text = "📝 اسامی افراد امروز برای جمع آوری وسایل :\n" + "\n".join([f"🔹 {name}" for name in names])
    keyboard = build_keyboard(names)
    await context.bot.send_message(chat_id=chat_id_to_send, text=text, reply_markup=keyboard)


async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    name_absent = query.data
    cycle_history = load_cycle_history()
    weekly_list_from_message = [button.callback_data for row in query.message.reply_markup.inline_keyboard for button in row]
    individuals, all_groups = load_names()
    all_possible_names = individuals + [name for group in all_groups for name in group]
    pool = [p for p in all_possible_names if p not in weekly_list_from_message]
    replacement = None
    if pool:
        replacement = random.choice(pool)
    if replacement:
        if name_absent in cycle_history:
            cycle_history.remove(name_absent)
        if replacement not in cycle_history:
            cycle_history.append(replacement)
        save_cycle_history(cycle_history)
    updated_weekly_list = weekly_list_from_message[:]
    if name_absent in updated_weekly_list:
        updated_weekly_list.remove(name_absent)
    if replacement:
        updated_weekly_list.append(replacement)
    new_text = "📝 اسامی بروز شده:\n"
    if replacement:
        new_text += f"_{name_absent}_ حذف شد و زحمتش افتاد به دوش _{replacement}_\n\n"
    new_text += "\n".join([f"🔹 {n}" for n in updated_weekly_list])
    new_keyboard = build_keyboard(updated_weekly_list)
    await query.edit_message_text(text=new_text, reply_markup=new_keyboard, parse_mode='Markdown')

async def reset_history_command(update: Update, context: CallbackContext):
    save_cycle_history([])
    await update.message.reply_text("✅ حافظه چرخه انتخاب اسامی با موفقیت پاک شد. چرخه از نو شروع خواهد شد.")

# این دستور اکنون تنها راه برای ارسال لیست است
async def test_command(update: Update, context: CallbackContext):
    config = load_config()
    chat_id = config.get("group_chat_id")
    
    if not chat_id:
        await update.message.reply_text("خطا: هنوز آیدی گروه تنظیم نشده! لطفا ابتدا ربات را به گروه اضافه کرده و از دستور /setup استفاده کنید.")
        return
        
    if update.effective_chat.id != chat_id:
        await update.message.reply_text("این دستور فقط باید در گروهی که ربات برای آن تنظیم شده، استفاده شود.")
        return

    await update.message.reply_text("باشه، الان یک لیست اسامی جدید در گروه ارسال می‌کنم...")
    await send_names(context, chat_id_to_send=chat_id)

async def track_chat_members(update: Update, context: CallbackContext) -> None:
    result = update.chat_member
    if result.new_chat_member.user.id == context.bot.id and result.new_chat_member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR]:
        chat_id = result.chat.id
        chat_title = result.chat.title
        print(f"INFO: Bot was added to group '{chat_title}' with ID: {chat_id}. Saving configuration.")
        
        config = load_config()
        config["group_chat_id"] = chat_id
        save_config(config)

        await context.bot.send_message(
            chat_id=chat_id, 
            text=(
                f"سلام! من در گروه '{chat_title}' با موفقیت فعال شدم ✅\n"
                "برای دریافت لیست افراد، از دستور /test استفاده کنید.\n"
                "الان یک نمونه لیست به صورت تستی می‌فرستم..."
            )
        )
        await send_names(context, chat_id_to_send=chat_id)

async def setup_command(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ این دستور فقط در گروه‌ها قابل اجراست.")
        return

    chat_id = chat.id
    chat_title = chat.title
    config = load_config()
    config["group_chat_id"] = chat_id
    save_config(config)
    
    await update.message.reply_text(
        f"✅ ربات با موفقیت برای گروه '{chat_title}' پیکربندی شد!\n"
        f"برای دریافت لیست اسامی از دستور /test استفاده کنید.\n"
        f"الان یک نمونه لیست به صورت تستی ارسال می‌کنم..."
    )
    await send_names(context, chat_id_to_send=chat_id)

def main():
    allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY, Update.CHAT_MEMBER]
    
    app = ApplicationBuilder().token(TOKEN).build()

    # --- Handlers ---
    app.add_handler(CommandHandler("setup", setup_command))
    app.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler("resethistory", reset_history_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    # --- بررسی کانفیگ در زمان اجرا ---
    config = load_config()
    chat_id = config.get("group_chat_id")

    print("Bot started and is running...")
    if not chat_id:
        print("WARNING: Group ID not configured. Please add the bot to a group and use /setup.")
    else:
        print(f"Bot is configured for group ID: {chat_id}")
    print("Use the /test command in the configured group to trigger the name list.")

    app.run_polling(allowed_updates=allowed_updates)


if __name__ == "__main__":
    main()