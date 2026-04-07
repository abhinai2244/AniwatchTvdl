#@cantarellabots
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, Message
from cantarella.button import Button as InlineKeyboardButton
import asyncio
import logging
from datetime import datetime

from cantarella.core.database import db
from cantarella.core.images import get_random_image
from cantarella.core.utils import decode_data
from config import OWNER_ID, START_PIC
from Script import Dead
from cantarella.telegram.decorators import check_ban, check_fsub

logger = logging.getLogger(__name__)

async def check_admin(filter, client, message):
    try:
        user_id = message.from_user.id
        if user_id == OWNER_ID:
            return True
        return await db.is_admin(user_id)
    except Exception as e:
        logger.error(f"Exception in check_admin: {e}")
        return False

admin = filters.create(check_admin)

@Client.on_message(filters.private & filters.command("manage") & admin)
@check_ban
@check_fsub
async def handle_settings(client: Client, message):
    ongoing_enabled = await db.get_user_setting(0, "ongoing_enabled", False)
    status_icon = "✅ ON" if ongoing_enabled else "❌ OFF"
    toggle_label = "🔴 Turn OFF" if ongoing_enabled else "🟢 Turn ON"

    caption = (
        "<blockquote><b>⚙️ ʙᴏᴛ ꜱᴇᴛᴛɪɴɢꜱ</b>\n\n"
        f"<b>📡 ᴏɴɢᴏɪɴɢ ᴀᴜᴛᴏ-ᴅᴏᴡɴʟᴏᴀᴅ:</b> {status_icon}\n\n"
        "ᴡʜᴇɴ ᴏɴ, ᴛʜᴇ ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄʜᴇᴄᴋꜱ ғᴏʀ ɴᴇᴡ ᴀɴɪᴍᴇ ᴇᴘɪꜱᴏᴅᴇꜱ ᴀɴᴅ ᴅᴏᴡɴʟᴏᴀᴅꜱ ᴛʜᴇᴍ.\n"
        "ᴡʜᴇɴ ᴏғғ, ᴏɴʟʏ ᴍᴀɴᴜᴀʟ ꜱᴇᴀʀᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ᴡᴏʀᴋꜱ.</blockquote>"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="toggle_ongoing"),
         InlineKeyboardButton("ᴄʟᴏꜱᴇ •", callback_data="close")
            ]
    ])
    await client.send_photo(
        message.chat.id,
        photo=get_random_image(),
        caption=caption,
        reply_markup=buttons,
        parse_mode=ParseMode.HTML
    )

@Client.on_message(filters.private & filters.command("autodel")  & admin)
@check_ban
@check_fsub
async def handle_autodel(client: Client, message):
    args = message.command
    if len(args) < 2:
        current_val = await db.get_user_setting(message.from_user.id, "autodel_time", 0)
        status = f"{current_val} ꜱᴇᴄᴏɴᴅꜱ" if current_val > 0 else "ᴅɪꜱᴀʙʟᴇᴅ"
        return await message.reply(
            f"<blockquote>🕒 <b>ᴄᴜʀʀᴇɴᴛ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ:</b> {status}\n\n"
            "ᴜꜱᴀɢᴇ: <code>/autodel 600</code> (ꜱᴇᴛꜱ ɪᴛ ᴛᴏ 10 ᴍɪɴᴜᴛᴇꜱ)\n"
            "ᴜꜱᴇ <code>/autodel 0</code> ᴛᴏ ᴅɪꜱᴀʙʟᴇ.</blockquote>",
            parse_mode=ParseMode.HTML
        )

    try:
        seconds = int(args[1])
        if seconds < 0:
            return await message.reply("<blockquote>❌ ᴘʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ᴀ ᴘᴏꜱɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ.</blockquote>", parse_mode=ParseMode.HTML)

        await db.set_user_setting(message.from_user.id, "autodel_time", seconds)

        if seconds > 0:
            mins = seconds // 60
            await message.reply(f"<blockquote>✅ <b>ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ꜱᴇᴛ:</b> {seconds} ꜱᴇᴄᴏɴᴅꜱ (~{mins} ᴍɪɴꜱ).\nғɪʟᴇꜱ ꜱᴇɴᴛ ᴛᴏ ʏᴏᴜʀ ᴘᴍ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ ᴛʜɪꜱ ᴛɪᴍᴇ.</blockquote>", parse_mode=ParseMode.HTML)
        else:
            await message.reply("<blockquote>✅ <b>ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴅɪꜱᴀʙʟᴇᴅ.</b></blockquote>", parse_mode=ParseMode.HTML)
    except ValueError:
        await message.reply("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ. ᴜꜱᴇ: <code>/autodel 600</code></blockquote>", parse_mode=ParseMode.HTML)

@Client.on_message(filters.command(["ongoing", "schedule"]))
@check_ban
@check_fsub
async def handle_ongoing_schedule(client: Client, message):
    from cantarella.telegram.ongoing import fetch_schedule_list

    status_msg = await client.send_photo(
        message.chat.id,
        photo=get_random_image(),
        caption="<blockquote>📆 <b>ғᴇᴛᴄʜɪɴɢ ᴛᴏᴅᴀʏ'ꜱ ᴀɴɪᴍᴇ ʀᴇʟᴇᴀꜱᴇ ꜱᴄʜᴇᴅᴜʟᴇ...</b></blockquote>",
        parse_mode=ParseMode.HTML
    )
    schedule = await asyncio.to_thread(fetch_schedule_list)

    if not schedule:
        await status_msg.edit_caption("<blockquote>❌ <b>ɴᴏ ᴀɴɪᴍᴇ ꜱᴄʜᴇᴅᴜʟᴇᴅ ғᴏʀ ᴛᴏᴅᴀʏ ᴏʀ ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ.</b></blockquote>", parse_mode=ParseMode.HTML)
        return

    date_str = datetime.now().strftime("%d %b %Y")
    text = f"<blockquote>📆 <b>ᴛᴏᴅᴀʏ'ꜱ ᴀɴɪᴍᴇ ʀᴇʟᴇᴀꜱᴇꜱ ꜱᴄʜᴇᴅᴜʟᴇ [{date_str}] [ɪꜱᴛ]</b>\n\n"

    for item in schedule:
        item_title = item['title']
        text += f"• <b>{item_title}</b>\n  🕒 ᴛɪᴍᴇ: {item['time']} ʜʀꜱ\n\n"
    text += "</blockquote>"

    await status_msg.edit_caption(text, parse_mode=ParseMode.HTML)

@Client.on_message(filters.private & filters.command("start"))
@check_ban
@check_fsub
async def handle_start(client: Client, message):
    # Handle deep-link file retrieval (no fsub needed for file links from channel)
    if len(message.command) > 1:
        data = message.command[1]
        try:
            decoded = decode_data(data)
            # Format: msgid_chatid OR startId-endId_chatid
            if "_" in decoded:
                msg_id_part, chat_id = decoded.split("_")
                status_msg = await client.send_message(message.chat.id, "<blockquote>🔄 <b>ғᴇᴛᴄʜɪɴɢ ғɪʟᴇꜱ...</b></blockquote>", parse_mode=ParseMode.HTML)

                try:
                    # Handle Auto-Delete if enabled
                    autodel_time = await db.get_user_setting(message.from_user.id, "autodel_time", 0)
                    notify_msg = None

                    if "-" in msg_id_part:
                        start_id, end_id = map(int, msg_id_part.split("-"))
                        for m_id in range(start_id, end_id + 1):
                            try:
                                copy_msg = await client.copy_message(
                                    chat_id=message.chat.id,
                                    from_chat_id=int(chat_id),
                                    message_id=m_id
                                )
                                if autodel_time > 0:
                                    from cantarella.telegram.download import schedule_deletion
                                    asyncio.create_task(schedule_deletion(client, message.chat.id, copy_msg.id, autodel_time))
                                await asyncio.sleep(0.3)
                            except Exception:
                                pass # skip if message deleted or not found
                    else:
                        copy_msg = await client.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=int(chat_id),
                            message_id=int(msg_id_part)
                        )
                        if autodel_time > 0:
                            from cantarella.telegram.download import schedule_deletion
                            asyncio.create_task(schedule_deletion(client, message.chat.id, copy_msg.id, autodel_time))

                    if autodel_time > 0:
                        mins = autodel_time // 60
                        notify_msg = await client.send_message(
                            message.chat.id,
                            f"<blockquote>🗑️ <b>ғɪʟᴇꜱ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ {mins} ᴍɪɴ ({autodel_time}ꜱ).</b>\n"
                            "ᴍᴀᴋᴇ ꜱᴜʀᴇ ᴛᴏ ꜱᴀᴠᴇ ᴛʜᴇᴍ ɪɴ ʏᴏᴜʀ 'ꜱᴀᴠᴇᴅ ᴍᴇꜱꜱᴀɢᴇꜱ' ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴋᴇᴇᴘ ᴛʜᴇᴍ!</blockquote>",
                            parse_mode=ParseMode.HTML
                        )
                        from cantarella.telegram.download import schedule_deletion
                        asyncio.create_task(schedule_deletion(client, message.chat.id, notify_msg.id, autodel_time))

                    await status_msg.delete()
                    return
                except Exception as e:
                    await status_msg.edit_text(f"<blockquote>❌ <b>ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ғɪʟᴇ:</b> {e}</blockquote>", parse_mode=ParseMode.HTML)
                    return
        except Exception:
            pass

    # Record user
    await db.add_user(message.from_user.id)

    buttons = []
    is_admin = await db.is_admin(message.from_user.id)
    if is_admin or message.from_user.id == OWNER_ID:
        buttons.append([
            InlineKeyboardButton("ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_panel"),
            InlineKeyboardButton("ᴛᴏɢɢʟᴇ ᴏɴɢᴏɪɴɢ", callback_data="toggle_ongoing")
        ])

    buttons.append([
        InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
        InlineKeyboardButton("Hᴇʟᴘ •", callback_data="help")
    ])

    inline_buttons = InlineKeyboardMarkup(buttons)

    try:
        await message.reply_photo(
            photo=START_PIC,
            caption=Dead.START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name or "",
                username="@" + message.from_user.username if message.from_user.username else None,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=inline_buttons
        )
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await message.reply_text("An error occurred while processing your request.")

@Client.on_message(filters.private & filters.command("help"))
@check_ban
@check_fsub
async def handle_help(client: Client, message):
    await db.add_user(message.from_user.id)
    inline_buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="start"),
                InlineKeyboardButton("ᴄʟᴏꜱᴇ •", callback_data="close")
            ]
        ]
    )
    try:
        await message.reply_photo(
            photo=START_PIC,
            caption=Dead.HELP_TXT.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name or "",
                username="@" + message.from_user.username if message.from_user.username else "ɴᴏɴᴇ",
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=inline_buttons
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await message.reply_text("An error occurred while processing your request.")