import asyncio
import logging

logger = logging.getLogger("DownSubBot")

class TaskQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.worker_task = None

    def start(self, process_callback):
        self.worker_task = asyncio.create_task(self._worker(process_callback))

    async def add_task(self, chat_id: int, message_id: int, status_msg_id: int, url: str, action: str, lang_name: str = None, srt_index: int = None):
        await self.queue.put((chat_id, message_id, status_msg_id, url, action, lang_name, srt_index))
        return self.queue.qsize()

    async def _worker(self, process_callback):
        while True:
            chat_id, message_id, status_msg_id, url, action, lang_name, srt_index = await self.queue.get()
            try:
                await process_callback(chat_id, message_id, status_msg_id, url, action, lang_name, srt_index)
            except Exception as e:
                logger.error(f"Error processing task for chat {chat_id}: {e}", exc_info=True)
            finally:
                self.queue.task_done()
