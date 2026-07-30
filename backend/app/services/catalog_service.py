import sqlite3
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any

from app.config import settings
from app.services.logger import setup_logger

logger = setup_logger(__name__)

CATALOG_DB_PATH = settings.paths.BASE_DIR / "catalog.db"

class CatalogService:
    """Service to maintain a local SQLite catalog of uploaded documents for the vector DB."""
    
    _local = threading.local()

    def __init__(self, db_path: Path = CATALOG_DB_PATH):
        self.db_path = db_path
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            # Ensure the directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """Initialize the database schema."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                chapter TEXT NOT NULL,
                filename TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def add_document(self, subject: str, chapter: str, filename: str, chunk_count: int) -> int:
        """Register a newly uploaded and embedded document into the catalog."""
        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT INTO documents (subject, chapter, filename, chunk_count) 
               VALUES (?, ?, ?, ?)''',
            (subject, chapter, filename, chunk_count)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_catalog_tree(self) -> Dict[str, Any]:
        """
        Returns a nested tree structure for the UI:
        {
            "Physics": {
                "name": "Physics",
                "chunk_count": 150,
                "children": {
                    "Electromagnetism": {
                        "name": "Electromagnetism",
                        "chunk_count": 50,
                    }
                }
            }
        }
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT subject, chapter, filename, chunk_count
            FROM documents
            ORDER BY subject, chapter, filename
        ''')
        rows = cursor.fetchall()
        
        tree = {}
        for row in rows:
            subject = row["subject"]
            chapter = row["chapter"]
            chunks = row["chunk_count"]
            
            if subject not in tree:
                tree[subject] = {"name": subject, "chunk_count": 0, "children": {}}
                
            tree[subject]["chunk_count"] += chunks
            
            if chapter not in tree[subject]["children"]:
                tree[subject]["children"][chapter] = {
                    "name": chapter,
                    "chunk_count": 0,
                }
                
            tree[subject]["children"][chapter]["chunk_count"] += chunks
            
        return tree
