"""
Telegram Admin Bot — Render.com
"""

import logging
import json
import os
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "admin_data.json"
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# ── KEEP ALIVE ────────────────────────────────────────────────────────────────
flask_app = Flask("")

@flask_app.route("/")
def home():
    return "Bot ishlayapti!", 200

@flask_app.route("/health")
def health():
    return {"status": "ok"}, 200

def keep_alive():
    Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False),
        daemon=True
    ).start()

# ── DATA ──────────────────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"bans": {}, "mutes": {}, "warns": {}, "logs": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

def log_action(action, admin, target, reason="", extra=""):
    data["logs"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action, "admin": admin,
        "target": target, "reason": reason, "extra": extra,
    })
    if len(data["logs"]) > 500:
        data["logs"] = data["logs"][-500:]
    save_data(data)

# ── HELPERS ───────────────────────────────────────────────────────────────────
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    return any(a.user.id == update.effective_user.id for a in admins)

async def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if context.args:
        arg = context.args[0]
        try:
            return await context.bot.get_chat(arg if arg.startswith("@") else int(arg))
        except Exception:
            return None
    return None

def ukey(chat_id, user_id):
    return f"{chat_id}:{user_id}"

def parse_dur(text) -> int | None:
    if not text: return None
    units = {"m": 60, "h": 3600, "d": 86400}
    if text[-1] in units and text[:-1].isdigit():
        return int(text[:-1]) * units[text[-1]]
    return None

# ── KEYBOARDS ─────────────────────────────────────────────────────────────────
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔨 Ban", callback_data="menu_ban"),
         InlineKeyboardButton("🔇 Mute", callback_data="menu_mute")],
        [InlineKeyboardButton("⚠️ Warn", callback_data="menu_warn"),
         InlineKeyboardButton("📋 Ro'yxat", callback_data="menu_list")],
        [InlineKeyboardButton("🔓 Unban", callback_data="menu_unban"),
         InlineKeyboardButton("🔊 Unmute", callback_data="menu_unmute")],
        [InlineKeyboardButton("📜 Tarix", callback_data="menu_logs"),
         InlineKeyboardButton("❌ Yopish", callback_data="menu_close")],
    ])

def ban_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔨 Reply ga Ban", callback_data="act_ban")],
        [InlineKeyboardButton("⏳ Vaqtli Ban", callback_data="act_tempban")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")],
    ])

def mute_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("30 daqiqa", callback_data="mute_30m"),
         InlineKeyboardButton("1 soat", callback_data="mute_1h")],
        [InlineKeyboardButton("1 kun", callback_data="mute_1d"),
         InlineKeyboardButton("7 kun", callback_data="mute_7d")],
        [InlineKeyboardButton("♾️ Doimiy", callback_data="mute_perm")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")],
    ])

def warn_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Warn ber", callback_data="act_warn")],
        [InlineKeyboardButton("✅ Warnni o'chir", callback_data="act_unwarn")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")],
    ])

def back_kb(to="menu_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data=to)]])

# ── COMMANDS ──────────────────────────────────────────────────────────────────
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    await update.message.reply_text("🛡️ *Admin Panel:*", reply_markup=main_kb(), parse_mode=ParseMode.MARKDOWN)

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Misol: `/ban @username sabab`", parse_mode=ParseMode.MARKDOWN); return
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "Ko'rsatilmagan"
    cid = update.effective_chat.id
    try:
        await context.bot.ban_chat_member(cid, t.id)
        data["bans"][ukey(cid, t.id)] = {"user_id": t.id, "username": t.username or t.first_name,
            "reason": reason, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "type": "permanent"}
        save_data(data)
        log_action("BAN", update.effective_user.full_name, t.username or str(t.id), reason)
        await update.message.reply_text(f"🔨 *Banned:* @{t.username or t.first_name}\n📝 {reason}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_tempban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❗ `/tempban @user 1h sabab`", parse_mode=ParseMode.MARKDOWN); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Topilmadi."); return
    secs = parse_dur(context.args[1])
    if not secs:
        await update.message.reply_text("❗ Vaqt: `30m` `1h` `1d` `7d`", parse_mode=ParseMode.MARKDOWN); return
    reason = " ".join(context.args[2:]) if len(context.args) > 2 else "Ko'rsatilmagan"
    cid = update.effective_chat.id
    until = datetime.now() + timedelta(seconds=secs)
    try:
        await context.bot.ban_chat_member(cid, t.id, until_date=until)
        data["bans"][ukey(cid, t.id)] = {"user_id": t.id, "username": t.username or t.first_name,
            "reason": reason, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "temp", "until": until.strftime("%Y-%m-%d %H:%M:%S")}
        save_data(data)
        log_action("TEMPBAN", update.effective_user.full_name, t.username or str(t.id), reason, context.args[1])
        await update.message.reply_text(
            f"⏳ *Vaqtli Ban:* @{t.username or t.first_name}\n📝 {reason}\n🕐 {context.args[1]}\n📅 {until.strftime('%Y-%m-%d %H:%M')}",
            parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Foydalanuvchini ko'rsating."); return
    cid = update.effective_chat.id
    try:
        await context.bot.unban_chat_member(cid, t.id)
        data["bans"].pop(ukey(cid, t.id), None); save_data(data)
        log_action("UNBAN", update.effective_user.full_name, t.username or str(t.id))
        await update.message.reply_text(f"🔓 *Unban:* @{t.username or t.first_name}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ `/mute @user 1h sabab`", parse_mode=ParseMode.MARKDOWN); return
    dur_str, reason = None, "Ko'rsatilmagan"
    if context.args and len(context.args) > 1:
        secs = parse_dur(context.args[1])
        if secs:
            dur_str = context.args[1]
            reason = " ".join(context.args[2:]) if len(context.args) > 2 else reason
        else:
            reason = " ".join(context.args[1:])
    no_perms = ChatPermissions(can_send_messages=False, can_send_media_messages=False,
        can_send_polls=False, can_send_other_messages=False, can_add_web_page_previews=False)
    until = datetime.now() + timedelta(seconds=parse_dur(dur_str)) if dur_str else None
    cid = update.effective_chat.id
    try:
        await context.bot.restrict_chat_member(cid, t.id, permissions=no_perms, until_date=until)
        data["mutes"][ukey(cid, t.id)] = {"user_id": t.id, "username": t.username or t.first_name,
            "reason": reason, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "temp" if until else "permanent",
            "until": until.strftime("%Y-%m-%d %H:%M:%S") if until else "doimiy"}
        save_data(data)
        log_action("MUTE", update.effective_user.full_name, t.username or str(t.id), reason, dur_str or "doimiy")
        msg = f"🔇 *Mute:* @{t.username or t.first_name}\n📝 {reason}\n🕐 {dur_str or 'Doimiy'}"
        if until: msg += f"\n📅 {until.strftime('%Y-%m-%d %H:%M')}"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Foydalanuvchini ko'rsating."); return
    full = ChatPermissions(can_send_messages=True, can_send_media_messages=True,
        can_send_polls=True, can_send_other_messages=True,
        can_add_web_page_previews=True, can_invite_users=True)
    cid = update.effective_chat.id
    try:
        await context.bot.restrict_chat_member(cid, t.id, permissions=full)
        data["mutes"].pop(ukey(cid, t.id), None); save_data(data)
        log_action("UNMUTE", update.effective_user.full_name, t.username or str(t.id))
        await update.message.reply_text(f"🔊 *Unmute:* @{t.username or t.first_name}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Foydalanuvchini ko'rsating."); return
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "Ko'rsatilmagan"
    cid = update.effective_chat.id
    key = ukey(cid, t.id)
    if key not in data["warns"]:
        data["warns"][key] = {"user_id": t.id, "username": t.username or t.first_name, "warns": []}
    data["warns"][key]["warns"].append({"reason": reason, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "admin": update.effective_user.full_name})
    wc = len(data["warns"][key]["warns"])
    save_data(data)
    log_action("WARN", update.effective_user.full_name, t.username or str(t.id), reason, f"#{wc}")
    msg = f"⚠️ *Warn:* @{t.username or t.first_name}\n📝 {reason}\n🔢 {wc}/3"
    if wc >= 3:
        try:
            await context.bot.ban_chat_member(cid, t.id)
            msg += "\n\n🔨 *3 warn — avtomatik ban!*"
            data["bans"][key] = {"user_id": t.id, "username": t.username or t.first_name,
                "reason": "3 warn", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "type": "auto_warn"}
            save_data(data)
            log_action("AUTO_BAN", "BOT", t.username or str(t.id), "3 warn")
        except Exception as e:
            msg += f"\n❌ Auto ban xato: {e}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Foydalanuvchini ko'rsating."); return
    key = ukey(update.effective_chat.id, t.id)
    if key in data["warns"] and data["warns"][key]["warns"]:
        data["warns"][key]["warns"].pop()
        if not data["warns"][key]["warns"]: data["warns"].pop(key)
        save_data(data)
        log_action("UNWARN", update.effective_user.full_name, t.username or str(t.id))
        await update.message.reply_text(f"✅ @{t.username or t.first_name} oxirgi warni o'chirildi.")
    else:
        await update.message.reply_text("ℹ️ Warn yo'q.")

async def cmd_warnlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    cid = update.effective_chat.id
    entries = [v for k, v in data["warns"].items() if k.startswith(f"{cid}:") and v["warns"]]
    if not entries:
        await update.message.reply_text("✅ Warn yo'q."); return
    await update.message.reply_text("⚠️ *Warnlar:*\n\n" + "\n".join(f"👤 @{e['username']} — {len(e['warns'])}/3" for e in entries), parse_mode=ParseMode.MARKDOWN)

async def cmd_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    cid = update.effective_chat.id
    entries = [v for k, v in data["bans"].items() if k.startswith(f"{cid}:")]
    if not entries:
        await update.message.reply_text("✅ Banlangan yo'q."); return
    await update.message.reply_text("🔨 *Banlangan:*\n\n" + "\n".join(f"👤 @{e['username']} | {e.get('type','?')} | {e['time'][:10]}" for e in entries), parse_mode=ParseMode.MARKDOWN)

async def cmd_mutelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    cid = update.effective_chat.id
    entries = [v for k, v in data["mutes"].items() if k.startswith(f"{cid}:")]
    if not entries:
        await update.message.reply_text("✅ Mute qilingan yo'q."); return
    await update.message.reply_text("🔇 *Mute:*\n\n" + "\n".join(f"👤 @{e['username']} | {e.get('until','?')}" for e in entries), parse_mode=ParseMode.MARKDOWN)

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    t = await get_target(update, context)
    if not t:
        await update.message.reply_text("❗ Foydalanuvchini ko'rsating."); return
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "Ko'rsatilmagan"
    cid = update.effective_chat.id
    try:
        await context.bot.ban_chat_member(cid, t.id)
        await context.bot.unban_chat_member(cid, t.id)
        log_action("KICK", update.effective_user.full_name, t.username or str(t.id), reason)
        await update.message.reply_text(f"👢 *Kick:* @{t.username or t.first_name}\n📝 {reason}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Siz admin emassiz."); return
    recent = data["logs"][-15:]
    if not recent:
        await update.message.reply_text("📜 Hali amal bajarilmagan."); return
    icons = {"BAN":"🔨","TEMPBAN":"⏳","UNBAN":"🔓","MUTE":"🔇","UNMUTE":"🔊","WARN":"⚠️","UNWARN":"✅","AUTO_BAN":"🤖","KICK":"👢"}
    lines = [f"📜 *Oxirgi {len(recent)} ta amal:*\n"]
    for l in reversed(recent):
        lines.append(f"{icons.get(l['action'],'📌')} `{l['time'][5:16]}` *{l['action']}* — @{l['target']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ *Admin Bot*\n\n/menu — Panel\n/ban @user sabab\n/tempban @user 1h sabab\n"
        "/unban @user\n/banlist\n/mute @user 1h sabab\n/unmute @user\n/mutelist\n"
        "/warn @user sabab\n/unwarn @user\n/warnlist\n/kick @user\n/logs",
        parse_mode=ParseMode.MARKDOWN)

# ── CALLBACKS ─────────────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cb = q.data

    if cb == "menu_main":
        await q.edit_message_text("🛡️ *Admin Panel:*", reply_markup=main_kb(), parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_ban":
        await q.edit_message_text("🔨 *Ban:*", reply_markup=ban_kb(), parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_mute":
        await q.edit_message_text("🔇 *Mute — muddat:*", reply_markup=mute_kb(), parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_warn":
        await q.edit_message_text("⚠️ *Warn:*", reply_markup=warn_kb(), parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_list":
        cid = q.message.chat_id
        bc = sum(1 for k in data["bans"] if k.startswith(f"{cid}:"))
        mc = sum(1 for k in data["mutes"] if k.startswith(f"{cid}:"))
        wc = sum(1 for k in data["warns"] if k.startswith(f"{cid}:"))
        await q.edit_message_text("📋 *Ro'yxatlar:*", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔨 Banlangan ({bc})", callback_data="list_bans")],
            [InlineKeyboardButton(f"🔇 Mute ({mc})", callback_data="list_mutes")],
            [InlineKeyboardButton(f"⚠️ Warnlar ({wc})", callback_data="list_warns")],
            [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_main")],
        ]), parse_mode=ParseMode.MARKDOWN)
    elif cb == "list_bans":
        cid = q.message.chat_id
        entries = [v for k, v in data["bans"].items() if k.startswith(f"{cid}:")]
        text = "🔨 *Banlangan:*\n\n" + "\n".join(f"• @{e['username']} | {e.get('type','?')} | {e['time'][:10]}" for e in entries[:20]) if entries else "✅ Yo'q."
        await q.edit_message_text(text, reply_markup=back_kb("menu_list"), parse_mode=ParseMode.MARKDOWN)
    elif cb == "list_mutes":
        cid = q.message.chat_id
        entries = [v for k, v in data["mutes"].items() if k.startswith(f"{cid}:")]
        text = "🔇 *Mute:*\n\n" + "\n".join(f"• @{e['username']} | {e.get('until','?')}" for e in entries[:20]) if entries else "✅ Yo'q."
        await q.edit_message_text(text, reply_markup=back_kb("menu_list"), parse_mode=ParseMode.MARKDOWN)
    elif cb == "list_warns":
        cid = q.message.chat_id
        entries = [v for k, v in data["warns"].items() if k.startswith(f"{cid}:") and v["warns"]]
        text = "⚠️ *Warnlar:*\n\n" + "\n".join(f"• @{e['username']} — {len(e['warns'])}/3" for e in entries[:20]) if entries else "✅ Yo'q."
        await q.edit_message_text(text, reply_markup=back_kb("menu_list"), parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_unban":
        await q.edit_message_text("🔓 `/unban @username`", parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_unmute":
        await q.edit_message_text("🔊 `/unmute @username`", parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_logs":
        recent = data["logs"][-10:]
        icons = {"BAN":"🔨","UNBAN":"🔓","MUTE":"🔇","UNMUTE":"🔊","WARN":"⚠️","KICK":"👢","AUTO_BAN":"🤖"}
        text = "📜 Hali amal yo'q." if not recent else "📜 *Oxirgi amallar:*\n\n" + "\n".join(
            f"{icons.get(l['action'],'📌')} {l['time'][5:16]} | *{l['action']}* @{l['target']}" for l in reversed(recent))
        await q.edit_message_text(text, reply_markup=back_kb(), parse_mode=ParseMode.MARKDOWN)
    elif cb == "menu_close":
        await q.delete_message()
    elif cb.startswith("mute_"):
        dk = cb.split("_")[1]
        label = {"30m":"30 daqiqa","1h":"1 soat","1d":"1 kun","7d":"7 kun","perm":"Doimiy"}.get(dk, dk)
        cmd = f"/mute @username {dk}" if dk != "perm" else "/mute @username"
        await q.edit_message_text(f"🔇 *{label}* — reply qilib:\n`{cmd} sabab`", parse_mode=ParseMode.MARKDOWN)
    elif cb in ("act_ban","act_tempban","act_warn","act_unwarn"):
        tips = {
            "act_ban":    "🔨 Reply qilib `/ban sabab`",
            "act_tempban":"⏳ `/tempban @user 1h sabab`\nVaqt: `30m` `1h` `1d` `7d`",
            "act_warn":   "⚠️ Reply qilib `/warn sabab`",
            "act_unwarn": "✅ Reply qilib `/unwarn`",
        }
        await q.edit_message_text(tips[cb], parse_mode=ParseMode.MARKDOWN)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()
    for name, fn in [
        ("menu", cmd_menu), ("help", cmd_help),
        ("ban", cmd_ban), ("tempban", cmd_tempban), ("unban", cmd_unban),
        ("mute", cmd_mute), ("unmute", cmd_unmute),
        ("warn", cmd_warn), ("unwarn", cmd_unwarn), ("warnlist", cmd_warnlist),
        ("banlist", cmd_banlist), ("mutelist", cmd_mutelist),
        ("kick", cmd_kick), ("logs", cmd_logs),
    ]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("✅ Bot ishga tushdi — Render.com")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
