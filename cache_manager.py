import sqlite3
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, db_path: str = 'data/cache.db', ttl: int = 3600):
        '''
        TTL - Time To Live в секундах (по умолчанию 1 час)
        '''
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.ttl = ttl
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)')
        conn.commit()
        conn.close()
        logger.info(f'✅ Cache initialized: {self.db_path}')
    
    def _get_key(self, query: str, query_type: str = 'general') -> str:
        '''енерация уникального ключа для запроса'''
        raw = f'{query_type}:{query}'.lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()
    
    def get(self, query: str, query_type: str = 'general') -> Optional[Dict[Any, Any]]:
        '''олучить данные из кэша'''
        key = self._get_key(query, query_type)
        now = int(time.time())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT value FROM cache WHERE key = ? AND expires_at > ?',
            (key, now)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            logger.info(f'🎯 Cache HIT: {query[:50]}...')
            return json.loads(row[0])
        
        logger.debug(f'❌ Cache MISS: {query[:50]}...')
        return None
    
    def set(self, query: str, value: Dict[Any, Any], query_type: str = 'general', ttl: int = None):
        '''Сохранить данные в кэш'''
        key = self._get_key(query, query_type)
        now = int(time.time())
        expires = now + (ttl if ttl else self.ttl)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'INSERT OR REPLACE INTO cache (key, value, created_at, expires_at) VALUES (?, ?, ?, ?)',
            (key, json.dumps(value), now, expires)
        )
        conn.commit()
        conn.close()
        logger.debug(f'💾 Cache SET: {query[:50]}...')
    
    def clear_expired(self):
        '''далить устаревшие записи'''
        now = int(time.time())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('DELETE FROM cache WHERE expires_at <= ?', (now,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            logger.info(f'🗑️ Cleared {deleted} expired cache entries')
        return deleted
    
    def clear_all(self):
        '''чистить весь кэш'''
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM cache')
        conn.commit()
        conn.close()
        logger.info('🗑️ Cache cleared')
    
    def get_stats(self) -> Dict[str, Any]:
        '''Статистика кэша'''
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT COUNT(*) FROM cache')
        total = cursor.fetchone()[0]
        
        now = int(time.time())
        cursor = conn.execute('SELECT COUNT(*) FROM cache WHERE expires_at > ?', (now,))
        valid = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_entries': total,
            'valid_entries': valid,
            'expired_entries': total - valid,
            'cache_file': str(self.db_path),
            'ttl_seconds': self.ttl
        }
