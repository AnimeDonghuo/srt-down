import re
import logging
from urllib.parse import urlparse
from unidecode import unidecode

logger = logging.getLogger("DownSubBot")

def get_provider(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        parts = domain.split(".")
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return domain.capitalize()
    except Exception:
        return "Unknown"

def sanitize_command_name(name: str) -> str:
    # Normalize unicode characters to plain ASCII (e.g., 'tiếng việt' -> 'tieng_viet')
    ascii_name = unidecode(name)
    clean = ascii_name.lower()
    # Replace spaces, dashes, brackets and symbols with underscores
    clean = re.sub(r'[\s\-()\[\]\.\+\,\/]+', '_', clean)
    clean = re.sub(r'[^a-z0-9_]', '', clean)
    clean = clean.strip('_')
    if not clean or clean[0].isdigit():
        clean = f"lang_{clean}"
    return clean

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def log_job(user_id, chat_id, url, provider, subtitle_count, duration, error=None):
    log_msg = (
        f"User ID: {user_id} | Chat ID: {chat_id} | URL: {url} | "
        f"Provider: {provider} | Subtitle Count: {subtitle_count} | "
        f"Duration: {duration:.2f}s"
    )
    if error:
        log_msg += f" | Error: {error}"
    logger.info(log_msg)
