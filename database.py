import sqlite3
import os
from contextlib import contextmanager

DB_NAME = "news_tracker.db"

@contextmanager
def get_db_connection():
    # Critical for APScheduler + Streamlit Cloud
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create companies table (with region support)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                region TEXT DEFAULT 'Global',
                last_status TEXT DEFAULT 'Pending first fetch'
            )
        ''')
        
        # Primitive Migration: Add region and last_status columns
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN region TEXT DEFAULT 'Global'")
        except sqlite3.OperationalError:
            pass 
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN last_status TEXT DEFAULT 'Pending first fetch'")
        except sqlite3.OperationalError:
            pass
        
        # Create articles table (link is UNIQUE to prevent duplicates)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                title TEXT,
                link TEXT UNIQUE,
                published_at TEXT,
                source TEXT,
                summary TEXT,
                sentiment TEXT,
                extraction_method TEXT DEFAULT 'summary',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        ''')
        # Primitive Migration: Add extraction_method column to articles
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN extraction_method TEXT DEFAULT 'summary'")
        except sqlite3.OperationalError:
            pass
        
        # Primitive Migration: Add summary and sentiment columns to articles
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN summary TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN sentiment TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Create a tiny status table to hold single app vars like last_fetch_time 
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()

def set_last_fetch_time(timestamp_iso: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO status (key, value) VALUES ('last_fetch_time', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        ''', (timestamp_iso,))
        conn.commit()

def get_last_fetch_time():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM status WHERE key='last_fetch_time'")
        row = cursor.fetchone()
        return row['value'] if row else None

def add_company(name: str, region: str = 'Global'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO companies (name, region, last_status) VALUES (?, ?, ?)', 
                           (name, region, 'Pending first fetch'))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # Already exists

def update_company_status(company_id: int, status: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE companies SET last_status = ? WHERE id = ?', (status, company_id))
        conn.commit()

def remove_company(name: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM companies WHERE name = ?', (name,))
        conn.commit()

def get_all_companies():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, region, last_status FROM companies ORDER BY name')
        return [dict(row) for row in cursor.fetchall()]

def add_article(company_id: int, title: str, link: str, published_at: str, source: str, summary: str = None, sentiment: str = None, extraction_method: str = 'summary'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO articles (company_id, title, link, published_at, source, summary, sentiment, extraction_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (company_id, title, link, published_at, source, summary, sentiment, extraction_method))
            conn.commit()
            return True # Successfully added
        except sqlite3.IntegrityError:
            return False # Duplicate link

def get_recent_articles(limit=50):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.title, a.link, a.published_at, a.source, a.summary, a.sentiment, a.extraction_method, c.name as company_name 
            FROM articles a
            JOIN companies c ON a.company_id = c.id
            ORDER BY a.created_at DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_articles_for_brand(company_name):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.title, a.link, a.published_at, a.source, a.summary, a.sentiment, a.extraction_method, c.name as company_name 
            FROM articles a
            JOIN companies c ON a.company_id = c.id
            WHERE c.name = ?
            ORDER BY a.published_at DESC
        ''', (company_name,))
        return [dict(row) for row in cursor.fetchall()]

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
