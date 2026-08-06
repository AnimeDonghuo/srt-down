import os
import asyncio
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger("DownSubBot")

class BrowserManager:
    _instance = None

    def __init__(self):
        self.playwright = None
        self.browser = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._init_browser()
        return cls._instance

    async def _init_browser(self):
        self.playwright = await async_playwright().start()
        # Launch options highly optimized for low-memory, single-core environments
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--single-process",
                "--disable-gpu",
                "--disable-extensions",
                "--mute-audio"
            ]
        )

    async def get_page(self):
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # Intercept advertisement popups or redirects and immediately close them
        context.on("page", lambda p: asyncio.create_task(p.close()))
        page = await context.new_page()
        return context, page

    async def get_safe_page(self):
        try:
            if not self.browser or not self.browser.is_connected():
                await self._init_browser()
            return await self.get_page()
        except Exception:
            try:
                await self.close_all()
            except Exception:
                pass
            await self._init_browser()
            return await self.get_page()

    async def close_all(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        BrowserManager._instance = None


async def scrape_downsub(url: str, download_dir: str, action: str, target_lang_name: str = None, srt_index: int = None):
    # action: "list", "all", or "single"
    manager = await BrowserManager.get_instance()
    context, page = await manager.get_safe_page()
    
    results = []
    video_title = "Video"
    
    try:
        encoded_url = quote_plus(url)
        target_url = f"https://downsub.com/?url={encoded_url}"
        logger.info(f"Retrieving: {target_url}")
        
        await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
        
        # Explicitly wait for standard DownSub subtitles elements to display
        try:
            await page.wait_for_selector("text=SRT", timeout=40000)
        except Exception:
            content = await page.content()
            if "not found" in content.lower() or "error" in content.lower() or "not support" in content.lower():
                raise Exception("DownSub does not support this link, or no subtitles are available.")
            raise Exception("Timeout reached waiting for results. DownSub may be under heavy load.")
        
        # Extract title from DownSub DOM structures
        video_title = await page.evaluate("""() => {
            let title = "Video";
            const durationEl = Array.from(document.querySelectorAll('*'))
                .find(el => el.textContent.includes('Duration:'));
            if (durationEl) {
                const prev = durationEl.previousElementSibling;
                if (prev && prev.textContent.trim()) {
                    title = prev.textContent.trim();
                }
            } else {
                const header = document.querySelector('h1, h2, h3, .title, [class*="title"]');
                if (header) {
                    title = header.textContent.trim();
                }
            }
            return title;
        }""")
        
        # Clean title to prevent path issues
        video_title = "".join(c for c in video_title if c.isalnum() or c in "._- ").strip()
        if not video_title:
            video_title = "Video"
            
        # Parse available languages and their sequential button indexes
        languages = await page.evaluate("""() => {
            const srtButtons = Array.from(document.querySelectorAll('button, a'))
                .filter(el => el.textContent.trim() === 'SRT');
            
            const results = [];
            srtButtons.forEach((btn, index) => {
                let parent = btn.parentElement;
                let languageText = "";
                
                for (let i = 0; i < 5; i++) {
                    if (!parent) break;
                    let clone = parent.cloneNode(true);
                    Array.from(clone.querySelectorAll('button, a')).forEach(el => el.remove());
                    const text = clone.textContent.trim().replace(/\\s+/g, ' ');
                    if (text && text.length > 1 && !text.includes('Settings')) {
                        languageText = text;
                        break;
                    }
                    parent = parent.parentElement;
                }
                
                if (!languageText) {
                    let sibling = btn.parentElement ? btn.parentElement.nextElementSibling : null;
                    while (sibling) {
                        const text = sibling.textContent.trim();
                        if (text && text.length > 1) {
                            languageText = text;
                            break;
                        }
                        sibling = sibling.nextElementSibling;
                    }
                }
                
                languageText = languageText.trim();
                if (languageText) {
                    results.push({
                        index: index,
                        language: languageText
                    });
                }
            });
            return results;
        }""")
        
        if action == "list":
            for lang_info in languages:
                results.append({
                    "language": lang_info["language"],
                    "file_path": None,
                    "srt_index": lang_info["index"]
                })
            return video_title, results
            
        # Execute file downloads
        os.makedirs(download_dir, exist_ok=True)
        # Match only SRT button elements
        srt_locators = page.locator("button:has-text('SRT'), a:has-text('SRT')")
        
        to_download = []
        if action == "single":
            matched_index = None
            if srt_index is not None:
                matched_index = srt_index
            else:
                for lang_info in languages:
                    if target_lang_name.lower() in lang_info["language"].lower():
                        matched_index = lang_info["index"]
                        break
            
            if matched_index is not None:
                for lang_info in languages:
                    if lang_info["index"] == matched_index:
                        to_download.append(lang_info)
                        break
        else: # action == "all"
            to_download = languages
            
        if not to_download:
            raise Exception("No matching subtitle tracks found.")
            
        for lang_info in to_download:
            idx = lang_info["index"]
            lang_name = lang_info["language"]
            
            try:
                # Expect a browser file download payload
                async with page.expect_download(timeout=30000) as download_info:
                    await srt_locators.nth(idx).click(timeout=15000)
                
                download = await download_info.value
                safe_lang = "".join(c for c in lang_name if c.isalnum() or c in "._- ").strip()
                filename = f"{video_title} - {safe_lang}.srt"
                dest_path = os.path.join(download_dir, filename)
                
                await download.save_as(dest_path)
                results.append({
                    "language": lang_name,
                    "file_path": dest_path,
                    "srt_index": idx
                })
            except Exception as e:
                logger.error(f"Failed to download language {lang_name}: {e}")
                
        return video_title, results
        
    finally:
        # Guarantee memory release by closing page and context instances immediately
        await page.close()
        await context.close()
