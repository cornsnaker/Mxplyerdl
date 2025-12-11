import asyncio
import os
import re
from config import NM3U8DL_PATH, USER_AGENT, ORIGIN

async def run_downloader(m3u8_url, output_path, progress_callback=None, quality=None):
    save_dir = os.path.dirname(output_path)
    save_name = os.path.splitext(os.path.basename(output_path))[0]

    cmd = [
        NM3U8DL_PATH,
        m3u8_url,
        "--save-dir", save_dir,
        "--save-name", save_name,
        "--header", f"User-Agent: {USER_AGENT}",
        "--header", f"Origin: {ORIGIN}",
        "--thread-count", "16",
        "--download-retry-count", "5",
        "-M", "format=mp4"
    ]

    if quality and quality != 'best':
        # quality is something like "1080p"
        # Extract number
        res = re.search(r'(\d+)', quality)
        if res:
             height = res.group(1)
             cmd.extend(["--select-video", f"res={height}"])

    # Run subprocess
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Monitor stdout for progress
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        line_str = line.decode('utf-8', errors='ignore').strip()
        if progress_callback and "%" in line_str:
             m = re.search(r'(\d+\.?\d*)%', line_str)
             if m:
                 await progress_callback(float(m.group(1)), line_str)

    await process.wait()
    return process.returncode == 0
