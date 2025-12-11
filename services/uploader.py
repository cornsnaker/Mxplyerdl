import aiohttp
import os
import asyncio

async def upload_file(bot, chat_id, file_path, caption=None, progress_callback=None):
    """
    Custom upload function to support progress callback.
    """
    file_size = os.path.getsize(file_path)

    # Check for Telegram Limit (50MB)
    if file_size > 49 * 1024 * 1024:
        raise Exception("File too large for Telegram API (>50MB). Needs Gofile or Local Server.")

    url = f"https://api.telegram.org/bot{bot.token}/sendVideo"

    filename = os.path.basename(file_path)

    # Simple generator for reading file with progress
    async def file_sender(f):
        chunk_size = 64 * 1024
        bytes_read = 0
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            if progress_callback:
                await progress_callback(bytes_read, file_size)
            yield chunk

    import aiofiles
    async with aiofiles.open(file_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('chat_id', str(chat_id))
        if caption:
            data.add_field('caption', caption)
        data.add_field('video', file_sender(f), filename=filename)

        async with aiohttp.ClientSession() as session:
             async with session.post(url, data=data, timeout=3600) as resp:
                 if resp.status != 200:
                     text = await resp.text()
                     raise Exception(f"Telegram API Error: {text}")
                 return await resp.json()
