import os
import asyncio
from aiogram import Bot, types
from aiogram.types import FSInputFile
from core.database import get_pending_queue, mark_completed
from services.mx_api import fetch, get_m3u8
from services.downloader import run_downloader
from services.uploader import upload_file
from config import BOT_TOKEN, ADMIN_IDS

async def progress_bar(current, total, status="Downloading"):
    percentage = current / total if total > 0 else 0
    filled = int(percentage * 10)
    bar = "▓" * filled + "░" * (10 - filled)
    return f"{status}: {bar} {int(percentage * 100)}%"

async def worker(bot: Bot):
    print("Worker started")
    while True:
        try:
            from core.database import DB_NAME
            import aiosqlite

            task = None
            async with aiosqlite.connect(DB_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM queue WHERE status = 'pending' ORDER BY id ASC LIMIT 1") as cursor:
                    task = await cursor.fetchone()

            if task:
                print(f"Processing task {task['id']} for user {task['user_id']}")
                await process_download_task(bot, task)
            else:
                await asyncio.sleep(5)

        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(5)

async def process_download_task(bot, task):
    user_id = task['user_id']
    url = task['url']
    queue_id = task['id']
    quality = task['quality']

    try:
        await bot.send_message(user_id, f"🚀 Starting download for: {task['title']}")

        # 1. Fetch Page
        html = await fetch(url)
        m3u8 = await get_m3u8(html)

        if not m3u8:
            await bot.send_message(user_id, "❌ Could not find media.")
            await mark_completed(queue_id)
            return

        # 2. Download
        out_path = f"mx_downloads_{user_id}/video_{queue_id}.mp4"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        status_msg = await bot.send_message(user_id, "⬇️ Downloading...")

        last_update = 0
        async def dl_progress(percent, text):
            nonlocal last_update
            import time
            if time.time() - last_update > 3:
                bar = await progress_bar(percent, 100, "Downloading")
                try:
                    await status_msg.edit_text(f"{bar}\n{text}")
                    last_update = time.time()
                except: pass

        success = await run_downloader(m3u8, out_path, dl_progress, quality=quality)

        if success:
            await status_msg.edit_text("⬆️ Uploading...")

            last_ul_update = 0
            async def ul_progress(current, total):
                nonlocal last_ul_update
                import time
                if time.time() - last_ul_update > 3:
                    bar = await progress_bar(current, total, "Uploading")
                    try:
                        await status_msg.edit_text(bar)
                        last_ul_update = time.time()
                    except: pass

            try:
                await upload_file(bot, user_id, out_path, caption=f"✅ {task['title']}", progress_callback=ul_progress)
            except Exception as e:
                await bot.send_message(user_id, f"❌ Upload failed: {e}")

            if os.path.exists(out_path):
                os.remove(out_path)
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Download failed.")

    except Exception as e:
        print(f"Task failed: {e}")
        await bot.send_message(user_id, f"❌ Error: {e}")
    finally:
        await mark_completed(queue_id)
