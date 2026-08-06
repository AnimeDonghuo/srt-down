import os
import shutil
import time
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import DOWNLOAD_DIR
from utils.helpers import get_provider, sanitize_command_name, is_valid_url, log_job
from utils.queue import TaskQueue
from automation.downloader import scrape_downsub

logger = logging.getLogger("DownSubBot")

session_state = {}
task_queue = TaskQueue()

def get_url_from_message(message: Message) -> str:
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    if len(parts) > 1 and is_valid_url(parts[1]):
        return parts[1]
    return ""

async def safe_edit_text(client: Client, chat_id: int, message_id: int, text: str):
    try:
        await client.edit_message_text(chat_id, message_id, text)
    except Exception:
        pass

def setup_handlers(bot: Client):
    task_queue.start(lambda *args: process_task(bot, *args))

    @bot.on_message(filters.command("start"))
    async def start_cmd(client: Client, message: Message):
        await message.reply_text(
            "👋 **DownSub Subtitle Downloader Bot**\n\n"
            "Send any supported video link (YouTube, Dailymotion, Viu, Viki, etc.) to automatically extract all subtitles.\n\n"
            "**Commands**:\n"
            "• `/list <url>` - Only list available language choices\n"
            "• `/all <url>` - Download and deliver every available subtitle language\n"
            "• Simply paste any URL to run the default `/all` flow."
        )

    @bot.on_message(filters.command("help"))
    async def help_cmd(client: Client, message: Message):
        await start_cmd(client, message)

    @bot.on_message(filters.command("list"))
    async def list_cmd(client: Client, message: Message):
        url = get_url_from_message(message)
        if not url:
            session = session_state.get(message.chat.id)
            if session:
                url = session["url"]
            else:
                await message.reply_text("❌ Please send a valid link with the command, e.g.: `/list https://dai.ly/xxxxxxxx`")
                return
        
        status_msg = await message.reply_text("⏳ Request placed in processing queue...")
        pos = await task_queue.add_task(
            chat_id=message.chat.id,
            message_id=message.id,
            status_msg_id=status_msg.id,
            url=url,
            action="list"
        )
        if pos > 1:
            await safe_edit_text(client, message.chat.id, status_msg.id, f"⏳ Request queued. Current line position: {pos - 1}")

    @bot.on_message(filters.command("all"))
    async def all_cmd(client: Client, message: Message):
        url = get_url_from_message(message)
        if not url:
            session = session_state.get(message.chat.id)
            if session:
                url = session["url"]
            else:
                await message.reply_text("❌ Please send a valid link with the command, e.g.: `/all https://dai.ly/xxxxxxxx`")
                return
        
        status_msg = await message.reply_text("⏳ Request placed in processing queue...")
        pos = await task_queue.add_task(
            chat_id=message.chat.id,
            message_id=message.id,
            status_msg_id=status_msg.id,
            url=url,
            action="all"
        )
        if pos > 1:
            await safe_edit_text(client, message.chat.id, status_msg.id, f"⏳ Request queued. Current line position: {pos - 1}")

    @bot.on_message(filters.text)
    async def text_handler(client: Client, message: Message):
        text = message.text.strip()
        
        # Intercept commands that represent potential dynamic languages
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command_name = parts[0][1:].lower()
            
            if command_name in ["start", "help", "all", "list"]:
                return
                
            chat_id = message.chat.id
            session = session_state.get(chat_id)
            if not session:
                await message.reply_text("❌ Session has expired or is inactive. Send a video link first.")
                return
                
            languages_map = session.get("languages", {})
            if command_name in languages_map:
                lang_info = languages_map[command_name]
                status_msg = await message.reply_text(f"⏳ Queued download for {lang_info['name']}...")
                pos = await task_queue.add_task(
                    chat_id=chat_id,
                    message_id=message.id,
                    status_msg_id=status_msg.id,
                    url=session["url"],
                    action="single",
                    lang_name=lang_info["name"],
                    srt_index=lang_info["index"]
                )
                if pos > 1:
                    await safe_edit_text(client, chat_id, status_msg.id, f"⏳ Request queued. Current line position: {pos - 1}")
            else:
                await message.reply_text(f"❌ Unknown command: `/{command_name}`. Run `/list` to check available choices.")
            return

        # Handle raw pasted URLs
        if is_valid_url(text):
            status_msg = await message.reply_text("⏳ Processing link input...")
            pos = await task_queue.add_task(
                chat_id=message.chat.id,
                message_id=message.id,
                status_msg_id=status_msg.id,
                url=text,
                action="all"
            )
            if pos > 1:
                await safe_edit_text(client, message.chat.id, status_msg.id, f"⏳ Request queued. Current line position: {pos - 1}")
        else:
            await message.reply_text("❌ Please enter a valid supported video URL.")


async def process_task(client: Client, chat_id: int, message_id: int, status_msg_id: int, url: str, action: str, lang_name: str = None, srt_index: int = None):
    start_time = time.time()
    provider = get_provider(url)
    
    # Establish a clean ephemeral directory for the specific job
    job_id = f"{chat_id}_{message_id}_{int(start_time)}"
    job_dir = os.path.join(DOWNLOAD_DIR, job_id)
    
    logger.info(f"Worker processing job: {job_id} | Action: {action} | Provider: {provider}")
    await safe_edit_text(client, chat_id, status_msg_id, "🔄 Connecting to DownSub engine...")
    
    try:
        if action == "list":
            title, results = await scrape_downsub(url, job_dir, "list")
            
            languages_dict = {}
            lines = []
            for item in results:
                lang = item["language"]
                idx = item["srt_index"]
                cmd = sanitize_command_name(lang)
                languages_dict[cmd] = {"name": lang, "index": idx}
                lines.append(f"• {lang} — /{cmd}")
            
            session_state[chat_id] = {
                "url": url,
                "title": title,
                "languages": languages_dict
            }
            
            subtitle_count = len(results)
            duration = time.time() - start_time
            
            if subtitle_count == 0:
                await safe_edit_text(client, chat_id, status_msg_id, "❌ No subtitles are available for this video.")
            else:
                response_text = (
                    f"🎬 **Video**: {title}\n"
                    f"🌍 **Provider**: {provider}\n"
                    f"💬 **Available Subtitles ({subtitle_count})**:\n\n" + "\n".join(lines) + "\n\n"
                    "👉 Run any of the commands listed above to download."
                )
                await safe_edit_text(client, chat_id, status_msg_id, response_text)
                
            log_job(chat_id, chat_id, url, provider, subtitle_count, duration)
            
        elif action in ["all", "single"]:
            await safe_edit_text(client, chat_id, status_msg_id, "🔍 Fetching and writing subtitle track(s)...")
            
            title, results = await scrape_downsub(
                url=url,
                download_dir=job_dir,
                action=action,
                target_lang_name=lang_name,
                srt_index=srt_index
            )
            
            # Map dynamic commands for download actions
            languages_dict = {}
            for item in results:
                lang = item["language"]
                idx = item["srt_index"]
                cmd = sanitize_command_name(lang)
                languages_dict[cmd] = {"name": lang, "index": idx}
            
            if chat_id not in session_state or action == "all":
                session_state[chat_id] = {
                    "url": url,
                    "title": title,
                    "languages": languages_dict
                }
            
            downloaded_count = len([r for r in results if r["file_path"] and os.path.exists(r["file_path"])])
            
            if downloaded_count == 0:
                await safe_edit_text(client, chat_id, status_msg_id, "❌ Downloading target subtitles failed.")
                duration = time.time() - start_time
                log_job(chat_id, chat_id, url, provider, 0, duration, error="Zero downloads completed")
                return
                
            await safe_edit_text(client, chat_id, status_msg_id, f"📤 Delivering {downloaded_count} files via Telegram...")
            
            for item in results:
                file_path = item["file_path"]
                lang = item["language"]
                
                if file_path and os.path.exists(file_path):
                    caption = (
                        f"🌍 **Language**: {lang}\n"
                        f"📝 **Format**: SRT\n"
                        f"🎬 **Video**: {title}"
                    )
                    try:
                        await client.send_document(
                            chat_id=chat_id,
                            document=file_path,
                            caption=caption,
                            reply_to_message_id=message_id
                        )
                    except Exception as upload_error:
                        logger.error(f"Failed to transmit file {file_path}: {upload_error}")
            
            await safe_edit_text(client, chat_id, status_msg_id, "✅ Subtitle download process completed.")
            duration = time.time() - start_time
            log_job(chat_id, chat_id, url, provider, downloaded_count, duration)
            
    except Exception as e:
        logger.error(f"Task runtime error: {e}", exc_info=True)
        await safe_edit_text(client, chat_id, status_msg_id, f"❌ Process encountered an issue:\n`{str(e)}`")
        duration = time.time() - start_time
        log_job(chat_id, chat_id, url, provider, 0, duration, error=str(e))
        
    finally:
        # Guarantee local file safety cleanups on Ephemeral filesystem
        shutil.rmtree(job_dir, ignore_errors=True)
