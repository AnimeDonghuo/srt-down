import asyncio
import logging
import os
import sys
from pyrogram import Client, idle
from config import API_ID, API_HASH, BOT_TOKEN, LOGS_DIR

# Set up logging before any imports
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

async def handle_health_check(reader, writer):
    """
    Extremely lightweight HTTP responder to satisfy Koyeb TCP/HTTP health probes.
    """
    try:
        # Read the incoming request header
        await reader.read(1024)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 2\r\n"
            "Connection: close\r\n"
            "\r\n"
            "OK"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()
    except Exception as e:
        logger.debug(f"Health check response error: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def start_health_server():
    """
    Reads Koyeb's assigned PORT environment variable and spawns a background server.
    """
    port_str = os.getenv("PORT", "8080")
    try:
        port = int(port_str)
    except ValueError:
        port = 8080

    try:
        server = await asyncio.start_server(handle_health_check, "0.0.0.0", port)
        logger.info(f"Health server successfully bound to 0.0.0.0:{port}")
        # Let the server run as a background task
        asyncio.create_task(server.serve_forever())
    except Exception as server_error:
        logger.error(f"Failed to start health server: {server_error}")

async def main():
    logger.info("Setting up Telegram bot environment...")
    
    bot = Client(
        "downsub_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )
    
    # Establish command routing triggers
    setup_handlers(bot)
    
    # Start the Koyeb HTTP Health Check Server
    await start_health_server()
    
    # Pre-spawn singleton browser process to speed up first interaction response
    logger.info("Initializing Chromium instance context...")
    try:
        await BrowserManager.get_instance()
        logger.info("Browser process initialized successfully.")
    except Exception as browser_init_error:
        logger.error(f"Browser environment fail: {browser_init_error}")
        
    logger.info("Launching Pyrogram engine...")
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
