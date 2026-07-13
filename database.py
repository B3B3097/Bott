import aiosqlite
import logging

DB_NAME = "data/bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS slots (
                slot_id    INTEGER PRIMARY KEY,
                is_occupied BOOLEAN DEFAULT 0,
                occupied_by INTEGER,
                post_id     INTEGER,
                expires_at  TIMESTAMP
            )
        ''')
        await db.execute('INSERT OR IGNORE INTO slots (slot_id) VALUES (1), (2)')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("price",   "1.0")')
        await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("timeout", "30")')
        await db.commit()
        logging.info("Database initialized.")

async def add_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id FROM users') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_price():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT value FROM settings WHERE key = "price"') as cursor:
            row = await cursor.fetchone()
            return float(row[0]) if row else 1.0

async def set_price(price: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE settings SET value = ? WHERE key = "price"', (str(price),))
        await db.commit()

async def get_timeout():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT value FROM settings WHERE key = "timeout"') as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 30

async def set_timeout(minutes: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE settings SET value = ? WHERE key = "timeout"', (str(minutes),))
        await db.commit()

async def get_free_slots():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT slot_id FROM slots WHERE is_occupied = 0') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_all_slots():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT slot_id, is_occupied, expires_at FROM slots ORDER BY slot_id'
        ) as cursor:
            return await cursor.fetchall()

async def occupy_slot(slot_id, user_id, post_id, expires_at):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE slots
            SET is_occupied = 1, occupied_by = ?, post_id = ?, expires_at = ?
            WHERE slot_id = ?
        ''', (user_id, post_id, expires_at, slot_id))
        await db.commit()

async def free_slot(slot_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE slots
            SET is_occupied = 0, occupied_by = NULL, post_id = NULL, expires_at = NULL
            WHERE slot_id = ?
        ''', (slot_id,))
        await db.commit()

async def get_occupied_slots():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            'SELECT slot_id, post_id, expires_at FROM slots WHERE is_occupied = 1'
        ) as cursor:
            return await cursor.fetchall()
