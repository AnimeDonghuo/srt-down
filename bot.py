import asyncio
import logging
import os
import sys
from pyrogram import Client, idle
from config import API_ID, API_HASH, BOT_TOKEN, LOGS_DIR

# Initialize log streams immediately on execution
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOGS_DIR, "bot.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("DownSubBot")

from handlers.commands import setup_handlers
from automation.downloader import BrowserManager

async def main():
    logger.info("Setting up Telegram bot environment...")
    
    bot = Client(
        "downsub_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )
    
    # Establish routing triggers
    setup_handlers(bot)
    
    # Pre-spawn singleton browser process to speed up first interaction response
    logger.info("Initializing Chromium instance context...")
    try:
        await BrowserManager.get_instance()
        logger.info("Browser process initialized successfully.")
    except Exception as browser_init_error:
        logger.error(f"Browser environment fail: {browser_init_error}")
        
    logger.info("Launching pyrogram engine...")
    await bot.start()
    
    logger.info("Bot execution started. Awaiting inputs...")
    await idle()
    
    # Tear down routines
    logger.info("System shutting down. Clearing context and instances...")
    await bot.stop()
    try:
        manager = await BrowserManager.get_instance()
        await manager.close_all()
    except Exception as stop_error:
        logger.error(f"Error when clearing browser processes: {stop_error}")
    logger.info("Shutdown routine complete.")

if __name__ == "__main__":
    asyncio.run(main())
