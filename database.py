import aiosqlite
import json
from datetime import datetime
from config import DATABASE_PATH

async def init_db():
    """Initialize the database"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_files INTEGER DEFAULT 0,
                total_lines INTEGER DEFAULT 0
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS processing_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT,
                file_size INTEGER,
                status TEXT DEFAULT 'pending',
                total_lines INTEGER DEFAULT 0,
                processed_lines INTEGER DEFAULT 0,
                found_lines INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS combo_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                line_number INTEGER,
                card_data TEXT,
                card_number TEXT,
                expiry TEXT,
                cvv TEXT,
                card_type TEXT,
                country TEXT,
                bank TEXT,
                is_valid INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES processing_tasks(id)
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_code TEXT UNIQUE,
                bank_name TEXT,
                card_type TEXT,
                country TEXT
            )
        ''')
        
        await db.commit()

async def get_user(user_id: int):
    """Get user from database"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(user_id: int, username: str, first_name: str):
    """Create new user"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
            (user_id, username, first_name)
        )
        await db.commit()

async def update_user_stats(user_id: int, files: int = 0, lines: int = 0):
    """Update user statistics"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            'UPDATE users SET total_files = total_files + ?, total_lines = total_lines + ? WHERE user_id = ?',
            (files, lines, user_id)
        )
        await db.commit()

async def create_task(user_id: int, filename: str, file_size: int):
    """Create new processing task"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO processing_tasks (user_id, filename, file_size) VALUES (?, ?, ?)',
            (user_id, filename, file_size)
        )
        await db.commit()
        return cursor.lastrowid

async def update_task(task_id: int, **kwargs):
    """Update task status"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        sets = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [task_id]
        await db.execute(f'UPDATE processing_tasks SET {sets} WHERE id = ?', values)
        await db.commit()

async def get_user_tasks(user_id: int, limit: int = 10):
    """Get user's recent tasks"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM processing_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            return await cursor.fetchall()

async def save_combo_result(task_id: int, line_number: int, card_data: str, 
                           card_number: str, expiry: str, cvv: str,
                           card_type: str, country: str, bank: str, is_valid: bool):
    """Save a single combo result"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            '''INSERT INTO combo_results 
               (task_id, line_number, card_data, card_number, expiry, cvv, card_type, country, bank, is_valid) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (task_id, line_number, card_data, card_number, expiry, cvv, 
             card_type, country, bank, 1 if is_valid else 0)
        )
        await db.commit()

async def save_combo_results_batch(task_id: int, results: list):
    """Save multiple combo results in batch for better performance"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executemany(
            '''INSERT INTO combo_results 
               (task_id, line_number, card_data, card_number, expiry, cvv, card_type, country, bank, is_valid) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            results
        )
        await db.commit()

async def get_task_results(task_id: int, limit: int = 100, offset: int = 0):
    """Get task results with pagination"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM combo_results WHERE task_id = ? LIMIT ? OFFSET ?',
            (task_id, limit, offset)
        ) as cursor:
            return await cursor.fetchall()

async def get_task_stats(task_id: int):
    """Get statistics for a task"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            '''SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) as valid,
                card_type,
                country
               FROM combo_results 
               WHERE task_id = ?
               GROUP BY card_type, country''',
            (task_id,)
        ) as cursor:
            return await cursor.fetchall()

async def clear_task_results(task_id: int):
    """Clear all results for a task"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('DELETE FROM combo_results WHERE task_id = ?', (task_id,))
        await db.commit()

async def search_bins(query: str):
    """Search BIN codes"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM banks WHERE bin_code LIKE ? LIMIT 10',
            (f'%{query}%',)
        ) as cursor:
            return await cursor.fetchall()
