import aiosqlite
from config import DB_NAME

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                custom_thumb TEXT,
                pref_quality TEXT DEFAULT '1080p',
                pref_audio TEXT DEFAULT 'Hindi',
                is_banned BOOLEAN DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                status TEXT DEFAULT 'pending',
                title TEXT,
                season INTEGER,
                episode INTEGER,
                quality TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def add_user(user_id, username, full_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)", (user_id, username, full_name))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_thumbnail(user_id, file_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET custom_thumb = ? WHERE id = ?", (file_id, user_id))
        await db.commit()

async def add_to_queue(user_id, url, title, season, episode, quality=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO queue (user_id, url, title, season, episode, quality) VALUES (?, ?, ?, ?, ?, ?)",
                         (user_id, url, title, season, episode, quality))
        await db.commit()

async def get_pending_queue(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM queue WHERE user_id = ? AND status = 'pending' ORDER BY id ASC", (user_id,)) as cursor:
            return await cursor.fetchall()

async def mark_completed(queue_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE queue SET status = 'completed' WHERE id = ?", (queue_id,))
        await db.commit()
