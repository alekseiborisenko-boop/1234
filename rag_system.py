# -*- coding: utf-8 -*-
"""
Unified RAG System with Training
Единая система RAG с runtime диалогами и ночным обучением
"""
import logging
import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import time
import requests
from bs4 import BeautifulSoup
import threading

logger = logging.getLogger(__name__)

# ChromaDB для векторного поиска
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    CHROMADB_AVAILABLE = True
except ImportError:
    logger.warning("ChromaDB or SentenceTransformers not available")
    CHROMADB_AVAILABLE = False


class UnifiedRAGSystem:
    """Единая система RAG: runtime + training"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # SQLite для метаданных
        self.db_path = self.data_dir / "knowledge.db"
        self.init_sqlite()
        
        # ChromaDB для векторного поиска
        if CHROMADB_AVAILABLE:
            self.chroma_path = self.data_dir / "chroma_db"
            self.chroma_path.mkdir(exist_ok=True)
            self.init_chromadb()
            self.embedder = SentenceTransformer(
                'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
            )
        else:
            self.chroma_client = None
            self.collections = {}
            self.embedder = None
        
        # Статус обучения
        self.training_active = False
        self.training_thread = None
        
        # Источники для обучения
        self.learning_sources = self._init_learning_sources()
        
        logger.info("✅ Unified RAG System initialized")
    
    def _init_learning_sources(self) -> Dict[str, List[str]]:
        """Инициализация источников обучения"""
        return {
            "wikipedia": [
                "Искусственный_интеллект", "Машинное_обучение", 
                "Python_(язык_программирования)", "Нейронная_сеть",
                "Обработка_естественного_языка", "Компьютерное_зрение",
                "Алгоритм", "Структура_данных", "Git", "Docker",
                "FastAPI", "PostgreSQL", "Redis", "Kubernetes"
            ],
            "programming_topics": [
                "Python async", "Docker compose", "REST API design",
                "Database optimization", "Git workflows", "CI/CD",
                "Machine learning pipelines", "Neural networks",
                "Vector embeddings", "RAG systems", "LLM prompting"
            ],
            "russian_topics": [
                "Башкортостан", "Уфа", "Российская_Федерация",
                "История_России", "Русский_язык", "Литература_России"
            ],
            "science": [
                "Физика", "Математика", "Химия", "Биология",
                "Астрономия", "Квантовая_механика", "Теория_вероятностей"
            ]
        }
    
    def init_sqlite(self):
        """Инициализация SQLite базы"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Таблица диалогов (runtime)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dialogues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL,
                model_used VARCHAR(50),
                success_rating FLOAT DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tags TEXT,
                collection VARCHAR(50) DEFAULT 'dialogues'
            )
        """)
        
        # Таблица обучающих данных (training)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source VARCHAR(100),
                topic VARCHAR(200),
                content_type VARCHAR(50),
                quality_score FLOAT DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                collection VARCHAR(50) DEFAULT 'training'
            )
        """)
        
        # Таблица истории обучения
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                cycles_completed INTEGER,
                items_added INTEGER,
                success_rate FLOAT,
                status VARCHAR(50)
            )
        """)
        
        # Индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dialogues_rating ON dialogues(success_rating)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_topic ON training_data(topic)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_quality ON training_data(quality_score)")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ SQLite database initialized")
    
    def init_chromadb(self):
        """Инициализация ChromaDB"""
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Коллекции
            self.collections = {
                "dialogues": self.chroma_client.get_or_create_collection("user_dialogues"),
                "training": self.chroma_client.get_or_create_collection("training_knowledge"),
                "code": self.chroma_client.get_or_create_collection("code_examples"),
                "solutions": self.chroma_client.get_or_create_collection("solutions"),
            }
            
            logger.info(f"✅ ChromaDB initialized")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self.chroma_client = None
            self.collections = {}
    
    # ==================== RUNTIME RAG ====================
    
    def add_dialogue(
        self,
        user_message: str,
        assistant_message: str,
        model_used: str = "unknown",
        success_rating: float = 0.5
    ) -> int:
        """Добавить диалог в базу (runtime)"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dialogues 
            (user_message, assistant_message, model_used, success_rating)
            VALUES (?, ?, ?, ?)
        """, (user_message, assistant_message, model_used, success_rating))
        
        dialogue_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Добавляем в ChromaDB
        if self.collections.get("dialogues") and self.embedder:
            try:
                text = f"USER: {user_message}\nASSISTANT: {assistant_message}"
                embedding = self.embedder.encode(text).tolist()
                
                self.collections["dialogues"].add(
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{
                        "model": model_used,
                        "rating": success_rating,
                        "db_id": dialogue_id,
                        "type": "dialogue"
                    }],
                    ids=[f"dialogue_{dialogue_id}_{int(time.time())}"]
                )
            except Exception as e:
                logger.error(f"Failed to add to ChromaDB: {e}")
        
        logger.debug(f"Added dialogue #{dialogue_id}")
        return dialogue_id
    
    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        collection: str = None
    ) -> List[Dict[str, Any]]:
        """Поиск в базе знаний"""
        if not self.collections or not self.embedder:
            return []
        
        try:
            query_embedding = self.embedder.encode(query).tolist()
            
            all_results = []
            
            # Ищем в указанной коллекции или во всех
            collections_to_search = (
                [self.collections[collection]] if collection and collection in self.collections
                else list(self.collections.values())
            )
            
            for coll in collections_to_search:
                try:
                    results = coll.query(
                        query_embeddings=[query_embedding],
                        n_results=3
                    )
                    
                    if results and results['documents']:
                        for i, doc in enumerate(results['documents'][0]):
                            metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                            distance = results['distances'][0][i] if results.get('distances') else 0
                            
                            similarity = 1.0 - min(distance / 2.0, 1.0)
                            
                            all_results.append({
                                "text": doc,
                                "similarity": round(similarity, 3),
                                "collection": coll.name,
                                "metadata": metadata
                            })
                except Exception as e:
                    logger.debug(f"Skip collection: {e}")
                    continue
            
            # Сортируем по similarity
            all_results.sort(key=lambda x: x["similarity"], reverse=True)
            return all_results[:limit]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    # ==================== TRAINING (WEB SCRAPING) ====================
    
    def scrape_wikipedia(self, topic: str) -> Optional[str]:
        """Парсинг Wikipedia"""
        url = f"https://ru.wikipedia.org/wiki/{topic}"
        
        try:
            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Удаляем ненужные элементы
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Извлекаем параграфы
            paragraphs = soup.find_all('p')
            text = '\n'.join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 100])
            
            return text[:5000] if text else None  # Первые 5000 символов
            
        except Exception as e:
            logger.error(f"Wikipedia scrape error for {topic}: {e}")
            return None
    
    def scrape_programming_content(self, query: str) -> Optional[str]:
        """Парсинг программистских ресурсов (симуляция)"""
        # В реальности здесь можно парсить:
        # - GitHub README
        # - Real Python articles
        # - GeeksforGeeks
        # - MDN Web Docs
        
        # Пока генерируем запрос к модели
        return f"Programming topic: {query}\n(Content would be scraped from real sources)"
    
    def add_training_content(
        self,
        content: str,
        source: str,
        topic: str,
        content_type: str = "article"
    ) -> int:
        """Добавить контент в базу обучения"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO training_data 
            (content, source, topic, content_type)
            VALUES (?, ?, ?, ?)
        """, (content, source, topic, content_type))
        
        content_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Добавляем в ChromaDB по чанкам
        if self.collections.get("training") and self.embedder:
            try:
                # Разбиваем на чанки
                chunk_size = 500
                chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
                
                for i, chunk in enumerate(chunks):
                    if len(chunk.strip()) < 50:
                        continue
                    
                    embedding = self.embedder.encode(chunk).tolist()
                    
                    self.collections["training"].add(
                        embeddings=[embedding],
                        documents=[chunk],
                        metadatas=[{
                            "source": source,
                            "topic": topic,
                            "type": content_type,
                            "db_id": content_id,
                            "chunk_id": i
                        }],
                        ids=[f"train_{content_id}_{i}_{int(time.time())}"]
                    )
                
                logger.debug(f"Added {len(chunks)} chunks for {topic}")
                
            except Exception as e:
                logger.error(f"Failed to add training content: {e}")
        
        return content_id
    
    def training_cycle(self) -> bool:
        """Один цикл обучения"""
        try:
            # Выбираем случайную категорию и тему
            import random
            category = random.choice(list(self.learning_sources.keys()))
            topics = self.learning_sources[category]
            topic = random.choice(topics)
            
            logger.info(f"📚 Training on: {category} / {topic}")
            
            # Парсим контент
            if category == "wikipedia":
                content = self.scrape_wikipedia(topic)
                source = "wikipedia"
            else:
                content = self.scrape_programming_content(topic)
                source = "web"
            
            if not content or len(content) < 100:
                logger.warning(f"Insufficient content for {topic}")
                return False
            
            # Добавляем в базу
            self.add_training_content(
                content=content,
                source=source,
                topic=topic,
                content_type="article"
            )
            
            logger.info(f"✅ Added {len(content)} chars for {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Training cycle error: {e}")
            return False
    
    def run_night_training(
        self,
        hours: int = 8,
        cycles_per_hour: int = 4
    ):
        """Ночное обучение"""
        self.training_active = True
        total_cycles = hours * cycles_per_hour
        interval = 3600 / cycles_per_hour
        
        # Записываем старт
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO training_history (started_at, status)
            VALUES (?, 'running')
        """, (datetime.now(),))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"🌙 NIGHT TRAINING STARTED")
        logger.info(f"Duration: {hours}h ({total_cycles} cycles)")
        
        success_count = 0
        
        for i in range(total_cycles):
            if not self.training_active:
                logger.info("Training stopped by user")
                break
            
            logger.info(f"🔄 Cycle {i+1}/{total_cycles}")
            
            if self.training_cycle():
                success_count += 1
            
            if i < total_cycles - 1:
                logger.info(f"😴 Sleeping {interval:.0f}s...\n")
                time.sleep(interval)
        
        # Завершение
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE training_history 
            SET finished_at = ?, cycles_completed = ?, 
                items_added = ?, success_rate = ?, status = 'completed'
            WHERE id = ?
        """, (
            datetime.now(),
            total_cycles,
            success_count,
            success_count / max(total_cycles, 1),
            session_id
        ))
        conn.commit()
        conn.close()
        
        self.training_active = False
        
        stats = self.get_stats()
        logger.info(f"\n🎉 TRAINING COMPLETED!")
        logger.info(f"Success rate: {success_count}/{total_cycles}")
        logger.info(f"Total items in DB: {stats}")
    
    def start_training_thread(
        self,
        hours: int = 8,
        cycles_per_hour: int = 4
    ) -> bool:
        """Запуск обучения в отдельном потоке"""
        if self.training_active:
            return False
        
        self.training_thread = threading.Thread(
            target=self.run_night_training,
            args=(hours, cycles_per_hour),
            daemon=True
        )
        self.training_thread.start()
        return True
    
    def stop_training(self):
        """Остановка обучения"""
        self.training_active = False
    
    # ==================== STATS ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        stats = {}
        
        # Подсчёт записей
        cursor.execute("SELECT COUNT(*) FROM dialogues")
        stats["dialogues"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM training_data")
        stats["training_items"] = cursor.fetchone()[0]
        
        # Размеры
        db_size = self.db_path.stat().st_size / (1024 * 1024)
        stats["db_size_mb"] = round(db_size, 2)
        
        if self.chroma_path.exists():
            chroma_size = sum(
                f.stat().st_size for f in self.chroma_path.rglob('*') if f.is_file()
            ) / (1024 * 1024)
            stats["chroma_size_mb"] = round(chroma_size, 2)
        
        # Статус обучения
        stats["training_active"] = self.training_active
        
        # История обучения
        cursor.execute("""
            SELECT COUNT(*), SUM(items_added), AVG(success_rate)
            FROM training_history
            WHERE status = 'completed'
        """)
        row = cursor.fetchone()
        stats["training_sessions"] = row[0] if row[0] else 0
        stats["total_trained_items"] = row[1] if row[1] else 0
        stats["avg_success_rate"] = round(row[2], 3) if row[2] else 0
        
        conn.close()
        return stats


# Глобальный экземпляр
rag_system = UnifiedRAGSystem()
