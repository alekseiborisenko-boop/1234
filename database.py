import sqlite3
import json
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = "/app/data/agent.db"

def init_database():
    """Инициализация базы данных"""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Таблица диалогов
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            query TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            model_used TEXT,
            rating INTEGER,
            context TEXT
        )
        ''')
        
        # Таблица знаний
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            content TEXT NOT NULL,
            source_url TEXT,
            confidence REAL DEFAULT 0.5,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0
        )
        ''')
        
        # Таблица настроек пользователей
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            preferred_model TEXT DEFAULT 'toucan',
            language TEXT DEFAULT 'ru',
            custom_instructions TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database initialized at {DB_PATH}")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

def save_conversation(query, answer, sources=None, model_used="toucan", user_id="default"):
    """Сохранение диалога"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO conversations (user_id, query, answer, sources, model_used)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, query, answer, json.dumps(sources) if sources else None, model_used))
        
        conn.commit()
        conversation_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"Conversation saved: ID={conversation_id}")
        return conversation_id
        
    except Exception as e:
        logger.error(f"Save conversation error: {e}")
        return None

def rate_conversation(conversation_id, rating):
    """Оценка ответа пользователем"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE conversations SET rating = ? WHERE id = ?', (rating, conversation_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Conversation {conversation_id} rated: {rating}")
        
    except Exception as e:
        logger.error(f"Rate conversation error: {e}")

def search_knowledge_base(query, limit=5):
    """Поиск в базе знаний"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Простой поиск по ключевым словам
        words = query.lower().split()
        results = []
        
        for word in words[:3]:  # Берём первые 3 слова
            cursor.execute('''
            SELECT topic, content, source_url, confidence 
            FROM knowledge_base 
            WHERE topic LIKE ? OR content LIKE ?
            ORDER BY confidence DESC, usage_count DESC
            LIMIT ?
            ''', (f'%{word}%', f'%{word}%', limit))
            
            results.extend(cursor.fetchall())
        
        conn.close()
        
        # Убираем дубликаты
        unique_results = []
        seen = set()
        for r in results:
            if r[0] not in seen:
                seen.add(r[0])
                unique_results.append({
                    'topic': r[0],
                    'content': r[1],
                    'source': r[2],
                    'confidence': r[3]
                })
        
        logger.info(f"Knowledge base search: found {len(unique_results)} results")
        return unique_results[:limit]
        
    except Exception as e:
        logger.error(f"Knowledge base search error: {e}")
        return []

def add_knowledge(topic, content, source_url, confidence=0.7):
    """Добавление знания в базу"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем дубликаты
        cursor.execute('SELECT id FROM knowledge_base WHERE topic = ? AND source_url = ?', (topic, source_url))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую запись
            cursor.execute('''
            UPDATE knowledge_base 
            SET content = ?, confidence = ?, last_updated = CURRENT_TIMESTAMP, usage_count = usage_count + 1
            WHERE id = ?
            ''', (content, confidence, existing[0]))
            logger.info(f"Knowledge updated: {topic}")
        else:
            # Добавляем новую запись
            cursor.execute('''
            INSERT INTO knowledge_base (topic, content, source_url, confidence)
            VALUES (?, ?, ?, ?)
            ''', (topic, content, source_url, confidence))
            logger.info(f"Knowledge added: {topic}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Add knowledge error: {e}")

def get_conversation_history(user_id="default", limit=10):
    """Получение истории диалогов"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT query, answer, timestamp, rating, model_used
        FROM conversations
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            'query': r[0], 
            'answer': r[1], 
            'timestamp': r[2], 
            'rating': r[3],
            'model': r[4]
        } for r in results]
        
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return []

def get_stats():
    """Получение статистики базы данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_conversations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM knowledge_base')
        total_knowledge = cursor.fetchone()[0]
        
        cursor.execute('SELECT AVG(rating) FROM conversations WHERE rating IS NOT NULL')
        avg_rating = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_conversations': total_conversations,
            'total_knowledge': total_knowledge,
            'avg_rating': round(avg_rating, 2)
        }
        
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return {}
