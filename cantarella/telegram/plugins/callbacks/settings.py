#@cantarellabots
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup
from cantarella.button import Button as InlineKeyboardButton
from config import *

# ─────────────────────────────────────────────
#  Toggle ongoing auto-download
# ─────────────────────────────────────────────

from cantarella.core.database import db

@Client.on_callback_query(filters.regex("^toggle_ongoing$"))
async def on_toggle_ongoing(client: Client, callback_query):
    is_admin = await db.is_admin(callback_query.from_user.id)
    if not is_admin and callback_query.from_user.id != OWNER_ID:
        return await callback_query.answer("❌ You are not authorized to use this.", show_alert=True)

    current_status = await db.get_user_setting(0, "ongoing_enabled", False)
    new_status = not current_status
    await db.set_user_setting(0, "ongoing_enabled", new_status)

    status_icon  = "✅ ᴏɴ"        if new_status else "❌ ᴏꜰꜰ"
    toggle_label = "🔴 ᴛᴜʀɴ ᴏꜰꜰ" if new_status else "🟢 ᴛᴜʀɴ ᴏɴ"
    action       = "ᴇɴᴀʙʟᴇᴅ"     if new_status else "ᴅɪꜱᴀʙʟᴇᴅ"

    caption = (
        "<blockquote><b>⚙️ ʙᴏᴛ ꜱᴇᴛᴛɪɴɢꜱ</b>\n\n"
        f"<b>📡 ᴏɴɢᴏɪɴɢ ᴀᴜᴛᴏ-ᴅᴏᴡɴʟᴏᴀᴅ:</b> {status_icon}\n\n"
        "ᴡʜᴇɴ ᴏɴ, ᴛʜᴇ ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄʜᴇᴄᴋꜱ ꜰᴏʀ ɴᴇᴡ ᴀɴɪᴍᴇ ᴇᴘɪꜱᴏᴅᴇꜱ ᴀɴᴅ ᴅᴏᴡɴʟᴏᴀᴅꜱ ᴛʜᴇᴍ.\n"
        "ᴡʜᴇɴ ᴏꜰꜰ, ᴏɴʟʏ ᴍᴀɴᴜᴀʟ ꜱᴇᴀʀᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ᴡᴏʀᴋꜱ.</blockquote>"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="toggle_ongoing"),
         InlineKeyboardButton("⬅️ ʙᴀᴄᴋ",  callback_data="start")]
    ])
    try:
        await callback_query.edit_message_caption(
            caption=caption,
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass
    await callback_query.answer(f"📡 ᴏɴɢᴏɪɴɢ ᴀᴜᴛᴏ-ᴅᴏᴡɴʟᴏᴀᴅ {action}!", show_alert=True)