[1mdiff --git a/main.py b/main.py[m
[1mold mode 100755[m
[1mnew mode 100644[m
[1mindex 7cb9a03..a203d74[m
[1m--- a/main.py[m
[1m+++ b/main.py[m
[36m@@ -1,1177 +1,6 @@[m
[31m-﻿import asyncio[m
[31m-import aiofiles[m
[32m+[m[32mfrom typing import List, Dict[m
[32m+[m[32mfrom fastapi import FastAPI, Request, HTTPException[m
[32m+[m[32mfrom duckduckgo_search import DDGS[m
 import logging[m
 import requests[m
[31m-import chromadb[m
[31m-from chromadb.config import Settings[m
[31m-from sentence_transformers import SentenceTransformer[m
[31m-import hashlib[m
[31m-import json[m
[31m-import time[m
[31m-import re[m
[31m-import os[m
[31m-import sys[m
[31m-from pathlib import Path[m
[31m-from datetime import datetime, timedelta[m
[31m-from fastapi import FastAPI, File, UploadFile, HTTPException, Request[m
[31m-from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse[m
[31m-from fastapi.staticfiles import StaticFiles[m
[31m-import GPUtil[m
[31m-import psutil[m
[31m-import subprocess[m
[31m-import yt_dlp[m
[31m-import sqlite3[m
[31m-import threading[m
[31m-from queue import Queue[m
[31m-import ast[m
[31m-import urllib.parse[m
[31m-from duckduckgo_search import DDGS[m
 from bs4 import BeautifulSoup[m
[31m-import wikipedia[m
[31m-import base64[m
[31m-import pytz[m
[31m-[m
[31m-# ==================== NEW SYSTEMS ====================[m
[31m-from test_system import test_system[m
[31m-from backup_system import backup_system[m
[31m-from model_hierarchy import model_hierarchy[m
[31m-[m
[31m-# Настройка логирования[m
[31m-logging.basicConfig([m
[31m-    level=logging.INFO,[m
[31m-    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',[m
[31m-    handlers=[[m
[31m-        logging.FileHandler('ii_agent.log', encoding='utf-8'),[m
[31m-        logging.StreamHandler()[m
[31m-    ][m
[31m-)[m
[31m-logger = logging.getLogger(__name__)[m
[31m-[m
[31m-# Константы[m
[31m-MODEL_TIMEOUT = 300  # 5 минут[m
[31m-MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB[m
[31m-CHROMA_DB_PATH = "/app/data/chroma_db"[m
[31m-BACKUP_DIR = Path("/app/data/backups")[m
[31m-BACKUP_DIR.mkdir(parents=True, exist_ok=True)[m
[31m-[m
[31m-# Проверка GPU[m
[31m-try:[m
[31m-    gpus = GPUtil.getGPUs()[m
[31m-    HAS_GPU = len(gpus) > 0[m
[31m-    if HAS_GPU:[m
[31m-        logger.info(f"GPU detected: {gpus[0].name}, VRAM: {gpus[0].memoryTotal}MB")[m
[31m-    else:[m
[31m-        logger.warning("GPU not detected")[m
[31m-except:[m
[31m-    HAS_GPU = False[m
[31m-    logger.warning("GPU detection failed")[m
[31m-[m
[31m-# Проверка chroma и sentence_transformers[m
[31m-try:[m
[31m-    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)[m
[31m-    embedder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')[m
[31m-    CHROMADB_AVAILABLE = True[m
[31m-    logger.info("✅ ChromaDB and SentenceTransformer initialized")[m
[31m-except Exception as e:[m
[31m-    CHROMADB_AVAILABLE = False[m
[31m-    logger.warning(f"⚠️ ChromaDB not available: {e}")[m
[31m-[m
[31m-# ==================== БАЗА ЗНАНИЙ ====================[m
[31m-def init_db():[m
[31m-    """Инициализация SQLite базы данных"""[m
[31m-    conn = sqlite3.connect('ii_agent.db')[m
[31m-    c = conn.cursor()[m
[31m-    [m
[31m-    # Таблица для диалогов[m
[31m-    c.execute('''CREATE TABLE IF NOT EXISTS conversations[m
[31m-                 (id INTEGER PRIMARY KEY AUTOINCREMENT,[m
[31m-                  user_id TEXT,[m
[31m-                  query TEXT,[m
[31m-                  response TEXT,[m
[31m-                  sources TEXT,[m
[31m-                  model_used TEXT,[m
[31m-                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,[m
[31m-                  rating INTEGER DEFAULT 0)''')[m
[31m-    [m
[31m-    # Таблица для базы знаний[m
[31m-    c.execute('''CREATE TABLE IF NOT EXISTS knowledge_base[m
[31m-                 (id INTEGER PRIMARY KEY AUTOINCREMENT,[m
[31m-                  topic TEXT,[m
[31m-                  content TEXT,[m
[31m-                  source TEXT,[m
[31m-                  confidence REAL DEFAULT 0.5,[m
[31m-                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')[m
[31m-    [m
[31m-    conn.commit()[m
[31m-    conn.close()[m
[31m-[m
[31m-def save_conversation(query, response, sources, model_used, user_id="default"):[m
[31m-    """Сохранение диалога в базу"""[m
[31m-    conn = sqlite3.connect('ii_agent.db')[m
[31m-    c = conn.cursor()[m
[31m-    c.execute("INSERT INTO conversations (user_id, query, response, sources, model_used) VALUES (?, ?, ?, ?, ?)",[m
[31m-              (user_id, query, response, json.dumps(sources), model_used))[m
[31m-    conn.commit()[m
[31m-    conversation_id = c.lastrowid[m
[31m-    conn.close()[m
[31m-    return conversation_id[m
[31m-[m
[31m-def add_knowledge(topic, content, source, confidence=0.7):[m
[31m-    """Добавление знания в базу"""[m
[31m-    conn = sqlite3.connect('ii_agent.db')[m
[31m-    c = conn.cursor()[m
[31m-    c.execute("INSERT OR REPLACE INTO knowledge_base (topic, content, source, confidence) VALUES (?, ?, ?, ?)",[m
[31m-              (topic, content, source, confidence))[m
[31m-    conn.commit()[m
[31m-    conn.close()[m
[31m-[m
[31m-def search_knowledge_base(query, limit=5):[m
[31m-    """Поиск по базе знаний"""[m
[31m-    if not CHROMADB_AVAILABLE:[m
[31m-        return [][m
[31m-    [m
[31m-    try:[m
[31m-        results = chroma_client.get_collection("knowledge_base").query([m
[31m-            query_texts=[query],[m
[31m-            n_results=limit[m
[31m-        )[m
[31m-        return [{'topic': r['topic'], 'content': r['content']} for r in results][m
[31m-    except:[m
[31m-        return [][m
[31m-[m
[31m-def get_conversation_history(user_id="default", limit=10):[m
[31m-    """Получение истории диалогов"""[m
[31m-    conn = sqlite3.connect('ii_agent.db')[m
[31m-    c = conn.cursor()[m
[31m-    c.execute("SELECT query, response, timestamp FROM conversations WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",[m
[31m-              (user_id, limit))[m
[31m-    history = c.fetchall()[m
[31m-    conn.close()[m
[31m-    return [{'query': h[0], 'response': h[1], 'timestamp': h[2]} for h in history][m
[31m-[m
[31m-def get_db_stats():[m
[31m-    """Статистика по базе данных"""[m
[31m-    conn = sqlite3.connect('ii_agent.db')[m
[31m-    c = conn.cursor()[m
[31m-    [m
[31m-    c.execute("SELECT COUNT(*) FROM conversations")[m
[31m-    total_conv = c.fetchone()[0][m
[31m-    [m
[31m-    c.execute("SELECT AVG(rating) FROM conversations WHERE rating > 0")[m
[31m-    avg_rating = c.fetchone()[0] or 0[m
[31m-    [m
[31m-    c.execute("SELECT COUNT(*) FROM knowledge_base")[m
[31m-    total_kb = c.fetchone()[0][m
[31m-    [m
[31m-    conn.close()[m
[31m-    return {[m
[31m-        'total_conversations': total_conv,[m
[31m-        'avg_rating': round(avg_rating, 2),[m
[31m-        'total_knowledge_base': total_kb[m
[31m-    }[m
[31m-[m
[31m-# Инициализация БД[m
[31m-init_db()[m
[31m-[m
[31m-# ==================== СИСТЕМНЫЕ МЕТРИКИ ====================[m
[31m-def get_system_metrics():[m
[31m-    """Получение метрик системы"""[m
[31m-    metrics = {[m
[31m-        'cpu_percent': psutil.cpu_percent(interval=1),[m
[31m-        'memory_percent': psutil.virtual_memory().percent,[m
[31m-        'disk_percent': psutil.disk_usage('/').percent,[m
[31m-        'timestamp': time.time()[m
[31m-    }[m
[31m-    [m
[31m-    if HAS_GPU:[m
[31m-        gpus = GPUtil.getGPUs()[m
[31m-        if gpus:[m
[31m-            gpu = gpus[0][m
[31m-            metrics.update({[m
[31m-                'gpu_percent': gpu.load * 100,[m
[31m-                'gpu_memory_percent': (gpu.memoryUsed / gpu.memoryTotal) * 100[m
[31m-            })[m
[31m-    [m
[31m-    return metrics[m
[31m-[m
[31m-# ==================== ПОИСК ПО ИНТЕРНЕТУ ====================[m
[31m-def is_valid_url(url):[m
[31m-    """Проверка валидности URL"""[m
[31m-    try:[m
[31m-        result = urllib.parse.urlparse(url)[m
[31m-        is_valid = all([result.scheme in ['http', 'https'], result.netloc])[m
[31m-        if not is_valid:[m
[31m-            logger.warning(f"Invalid URL: {url}")[m
[31m-            return False[m
[31m-        if any(char in url for char in [' ', '<', '>', '"', '{', '}']):[m
[31m-            logger.warning(f"Invalid chars in URL: {url}")[m
[31m-            return False[m
[31m-        logger.debug(f"Valid URL: {url}")[m
[31m-        return True[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"URL validation error: {e}")[m
[31m-        return False[m
[31m-[m
[31m-def extract_and_validate_urls(text):[m
[31m-    """Извлечение и валидация URL из текста"""[m
[31m-    logger.info("Extracting URLs...")[m
[31m-    potential_urls = re.findall(r'https?://[^\s]+', text)[m
[31m-    valid_urls = [][m
[31m-    [m
[31m-    for url in potential_urls:[m
[31m-        url = url.rstrip('.,;:!?)')[m
[31m-        if is_valid_url(url):[m
[31m-            valid_urls.append(url)[m
[31m-        else:[m
[31m-            logger.warning(f"Skipping: {url}")[m
[31m-    [m
[31m-    logger.info(f"Extracted {len(valid_urls)}/{len(potential_urls)} valid URLs")[m
[31m-    return valid_urls[m
[31m-[m
[31m-def parse_url_deep(url):[m
[31m-    """Глубокий парсинг URL с обработкой различных форматов"""[m
[31m-    logger.info(f"Parsing: {url}")[m
[31m-    try:[m
[31m-        headers = {[m
[31m-            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'[m
[31m-        }[m
[31m-        response = requests.get(url, headers=headers, timeout=15)[m
[31m-        response.raise_for_status()[m
[31m-        [m
[31m-        # Проверяем тип контента[m
[31m-        content_type = response.headers.get('content-type', '').lower()[m
[31m-        if 'application/pdf' in content_type:[m
[31m-            # Обработка PDF[m
[31m-            return [{'title': 'PDF Content', 'content': 'PDF content extraction not implemented yet'}][m
[31m-        [m
[31m-        soup = BeautifulSoup(response.content, 'html.parser')[m
[31m-        [m
[31m-        # Удаляем ненужные элементы[m
[31m-        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):[m
[31m-            tag.decompose()[m
[31m-        [m
[31m-        title = soup.find('title')[m
[31m-        title = title.get_text().strip() if title else 'No Title'[m
[31m-        [m
[31m-        # Извлекаем основной контент[m
[31m-        content_selectors = [[m
[31m-            'article', 'main', '.content', '.post', '.entry-content',[m
[31m-            '.article-body', '[role="main"]', 'body'[m
[31m-        ][m
[31m-        [m
[31m-        content = ""[m
[31m-        for selector in content_selectors:[m
[31m-            element = soup.select_one(selector)[m
[31m-            if element:[m
[31m-                content = element.get_text(separator=' ', strip=True)[m
[31m-                break[m
[31m-        [m
[31m-        if not content:[m
[31m-            content = soup.get_text(separator=' ', strip=True)[m
[31m-        [m
[31m-        # Ограничиваем длину[m
[31m-        content = content[:2000] if len(content) > 2000 else content[m
[31m-        [m
[31m-        return [{'title': title, 'content': content}][m
[31m-        [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Parse error: {e}")[m
[31m-        return [][m
[31m-[m
[31m-def search_google_api(query, num=5):[m
[31m-    """Google Custom Search API (если настроено)"""[m
[31m-    api_key = os.getenv("GOOGLE_API_KEY")[m
[31m-    cse_id = os.getenv("GOOGLE_CSE_ID")[m
[31m-    [m
[31m-    if not api_key or not cse_id:[m
[31m-        logger.debug("Google API not configured")[m
[31m-        return [][m
[31m-    [m
[31m-    try:[m
[31m-        url = "https://www.googleapis.com/customsearch/v1"[m
[31m-        params = {[m
[31m-            'key': api_key,[m
[31m-            'cx': cse_id,[m
[31m-            'q': query,[m
[31m-            'num': num[m
[31m-        }[m
[31m-        response = requests.get(url, params=params, timeout=10)[m
[31m-        response.raise_for_status()[m
[31m-        [m
[31m-        data = response.json()[m
[31m-        results = [][m
[31m-        for item in data.get('items', []):[m
[31m-            results.append({[m
[31m-                'title': item.get('title', ''),[m
[31m-                'url': item.get('link', ''),[m
[31m-                'snippet': item.get('snippet', ''),[m
[31m-                'priority': 1[m
[31m-            })[m
[31m-        return results[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Google API error: {e}")[m
[31m-        return [][m
[31m-[m
[31m-def search_wikipedia(query, sentences=3):[m
[31m-    """Поиск в Wikipedia"""[m
[31m-    try:[m
[31m-        # Устанавливаем язык (по умолчанию русский)[m
[31m-        wikipedia.set_lang("ru")[m
[31m-        page = wikipedia.page(query)[m
[31m-        summary = wikipedia.summary(query, sentences=sentences)[m
[31m-        return [{[m
[31m-            'title': page.title,[m
[31m-            'url': page.url,[m
[31m-            'snippet': summary,[m
[31m-            'priority': 2[m
[31m-        }][m
[31m-    except:[m
[31m-        try:[m
[31m-            # Поиск похожих страниц[m
[31m-            search_results = wikipedia.search(query, results=1)[m
[31m-            if search_results:[m
[31m-                page = wikipedia.page(search_results[0])[m
[31m-                summary = wikipedia.summary(search_results[0], sentences=sentences)[m
[31m-                return [{[m
[31m-                    'title': page.title,[m
[31m-                    'url': page.url,[m
[31m-                    'snippet': summary,[m
[31m-                    'priority': 2[m
[31m-                }][m
[31m-        except:[m
[31m-            pass[m
[31m-    return [][m
[31m-[m
[31m-def search_duckduckgo(query, max_results=5):[m
[31m-    """Поиск через DuckDuckGo"""[m
[31m-    try:[m
[31m-        with DDGS() as ddgs:[m
[31m-            results = ddgs.text(query, max_results=max_results)[m
[31m-            formatted_results = [][m
[31m-            for r in results:[m
[31m-                formatted_results.append({[m
[31m-                    'title': r.get('title', ''),[m
[31m-                    'url': r.get('href', ''),[m
[31m-                    'snippet': r.get('body', ''),[m
[31m-                    'priority': 3[m
[31m-                })[m
[31m-            return formatted_results[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"DDG error: {e}")[m
[31m-        return [][m
[31m-[m
[31m-def search_multi_engine(query):[m
[31m-    """Мульти-поиск через все доступные движки"""[m
[31m-    logger.info(f"Multi-search: {query}")[m
[31m-    all_sources = [][m
[31m-    [m
[31m-    # Google API (если настроено)[m
[31m-    google = search_google_api(query, 3)[m
[31m-    all_sources.extend(google)[m
[31m-    logger.info(f"Google: {len(google)} results")[m
[31m-    [m
[31m-    # Wikipedia[m
[31m-    wiki = search_wikipedia(query)[m
[31m-    all_sources.extend(wiki)[m
[31m-    logger.info(f"Wikipedia: {len(wiki)} results")[m
[31m-    [m
[31m-    # DuckDuckGo[m
[31m-    ddg = search_duckduckgo(query, 5)[m
[31m-    all_sources.extend(ddg)[m
[31m-    logger.info(f"DDG: {len(ddg)} results")[m
[31m-    [m
[31m-    logger.info(f"Total: {len(all_sources)} results")[m
[31m-    return all_sources[m
[31m-[m
[31m-# ==================== АГРЕГАЦИЯ ====================[m
[31m-def aggregate_and_respond(sources, query, model_name, use_cloud=False, cloud_model="auto"):[m
[31m-    """Агрегация информации из источников через модель"""[m
[31m-    if not sources:[m
[31m-        logger.warning("No sources for aggregation")[m
[31m-        return "Не удалось найти информацию."[m
[31m-    [m
[31m-    logger.info(f"Aggregating {len(sources)} sources")[m
[31m-    context = "\n-".join([f"ИСТОЧНИК {i+1}:\nURL: {s.get('url', s.get('source', 'KB'))}\nЗаголовок: {s.get('title', s.get('topic', ''))}\nТекст: {s.get('content', s.get('snippet', ''))[:500]}" for i, s in enumerate(sources[:5])])[m
[31m-    [m
[31m-    prompt = f"""Ты - ассистент, который отвечает на вопросы используя ТОЛЬКО релевантные источники.[m
[31m-[m
[31m-ВОПРОС: {query}[m
[31m-[m
[31m-НАЙДЕННЫЕ ИСТОЧНИКИ:[m
[31m-{context}[m
[31m-[m
[31m-ИНСТРУКЦИЯ:[m
[31m-1. Проверь релевантность каждого источника вопросу[m
[31m-2. Используй ТОЛЬКО те источники, которые НАПРЯМУЮ отвечают на вопрос[m
[31m-3. Игнорируй источники о другой теме[m
[31m-4. Если нет релевантных источников — напиши "Источники не содержат информации о [тема]"[m
[31m-5. В конце добавь "**Источники:**" со списком URL[m
[31m-[m
[31m-ВАЖНО: НЕ ПРИДУМЫВАЙ информацию, которой нет в источниках![m
[31m-Отвечай ТОЛЬКО на русском языку. БЕЗ вступлений типа "Конечно", "Вот ответ".[m
[31m-"""[m
[31m-[m
[31m-    logger.debug(f"Aggregation prompt: {len(prompt)} chars")[m
[31m-    [m
[31m-    # Выбор модели[m
[31m-    if use_cloud:[m
[31m-        logger.info(f"Using cloud: {cloud_model}")[m
[31m-        response = call_cloud_model(prompt, model_name=cloud_model, max_tokens=1500)[m
[31m-        if not response:[m
[31m-            logger.warning("Cloud failed, fallback to local")[m
[31m-            response = call_model(prompt, model_name, timeout=300)[m
[31m-        else:[m
[31m-            model_name = f"cloud:{cloud_model}"[m
[31m-    else:[m
[31m-        response = call_model(prompt, model_name, timeout=300)[m
[31m-    [m
[31m-    # Добавляем источники если модель забыла[m
[31m-    if "**Источники:**" not in response:[m
[31m-        sources_text = "\n**Источники:**\n" + "\n".join([f"- {s.get('url', s.get('source', ''))}" for s in sources[:5]])[m
[31m-        response += sources_text[m
[31m-    [m
[31m-    # Сохранение в БД[m
[31m-    sources_urls = [s.get('url', s.get('source', '')) for s in sources][m
[31m-    conversation_id = save_conversation(query, response, sources_urls, model_name)[m
[31m-    [m
[31m-    # Сохранение знаний[m
[31m-    for source in sources[:3]:[m
[31m-        if 'url' in source and 'content' in source and len(source['content']) > 100:[m
[31m-            topic = source.get('title', query.split()[0])[:100][m
[31m-            add_knowledge(topic, source['content'][:500], source['url'], confidence=0.7)[m
[31m-    [m
[31m-    logger.info(f"Saved: ID={conversation_id}")[m
[31m-    return response[m
[31m-# ==================== МОДЕЛИ ====================[m
[31m-def call_model(prompt, model_name="qwen2.5:7b-instruct-q5_K_M", timeout=None):[m
[31m-    """Вызов локальной модели через Ollama"""[m
[31m-    if timeout is None:[m
[31m-        timeout = MODEL_TIMEOUT[m
[31m-        [m
[31m-    try:[m
[31m-        # ✅ ИСПРАВЛЕНИЕ: Автоматическая замена неполных имён моделей[m
[31m-        model_fixes = {[m
[31m-            'toucan': 'toucan:latest',[m
[31m-            'llava': 'llava:7b',[m
[31m-            'qwen2.5': 'qwen2.5:7b-instruct-q4_K_M',[m
[31m-            'granite-code': 'granite-code:3b',[m
[31m-            'qwen2.5-coder': 'qwen2.5-coder:7b',[m
[31m-            'nomic-embed-text': 'nomic-embed-text:latest',[m
[31m-        }[m
[31m-        actual_model_name = model_fixes.get(model_name, model_name)[m
[31m-        [m
[31m-        logger.info(f"Calling model: {actual_model_name}")[m
[31m-        [m
[31m-        response = requests.post([m
[31m-            "http://host.docker.internal:11434/api/generate",[m
[31m-            json={[m
[31m-                "model": actual_model_name,[m
[31m-                "prompt": prompt,[m
[31m-                "stream": False,[m
[31m-                "options": {[m
[31m-                    "temperature": 0.3,[m
[31m-                    "top_p": 0.9,[m
[31m-                    "max_tokens": 1500,[m
[31m-                    "num_ctx": 4096[m
[31m-                }[m
[31m-            },[m
[31m-            timeout=timeout[m
[31m-        )[m
[31m-        [m
[31m-        if response.status_code == 200:[m
[31m-            result = response.json()[m
[31m-            logger.info(f"Model {actual_model_name} response: {len(result.get('response', ''))} chars")[m
[31m-            return result.get("response", "")[m
[31m-        else:[m
[31m-            logger.error(f"Model {actual_model_name} error: {response.status_code}")[m
[31m-            return f"❌ Ошибка модели: {response.status_code}"[m
[31m-            [m
[31m-    except requests.Timeout:[m
[31m-        logger.error(f"Model {actual_model_name} timeout")[m
[31m-        return "❌ Таймаут модели"[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Call model error: {e}")[m
[31m-        return f"❌ Ошибка: {e}"[m
[31m-[m
[31m-def call_cloud_model(prompt, model_name="gpt-4o-mini", max_tokens=1000):[m
[31m-    """Вызов облачной модели (GPT, Claude, Gemini)"""[m
[31m-    try:[m
[31m-        api_key = os.getenv("OPENAI_API_KEY") # Используем OPENAI_API_KEY для GPT и других через прокси[m
[31m-        if not api_key:[m
[31m-            logger.warning("Cloud API key not set")[m
[31m-            return ""[m
[31m-        [m
[31m-        headers = {[m
[31m-            "Authorization": f"Bearer {api_key}",[m
[31m-            "Content-Type": "application/json"[m
[31m-        }[m
[31m-        [m
[31m-        payload = {[m
[31m-            "model": model_name,[m
[31m-            "messages": [{"role": "user", "content": prompt}],[m
[31m-            "max_tokens": max_tokens,[m
[31m-            "temperature": 0.3[m
[31m-        }[m
[31m-        [m
[31m-        # Используем прокси для доступа к облачным API, если они настроены[m
[31m-        proxy_url = os.getenv("CLOUD_API_PROXY_URL")[m
[31m-        if proxy_url:[m
[31m-            url = proxy_url[m
[31m-            payload["provider"] = model_name.split('-')[0] # Пример: gpt, claude[m
[31m-        else:[m
[31m-            url = "https://api.openai.com/v1/chat/completions"[m
[31m-        [m
[31m-        response = requests.post(url, headers=headers, json=payload, timeout=60)[m
[31m-        [m
[31m-        if response.status_code == 200:[m
[31m-            result = response.json()[m
[31m-            content = result['choices'][0]['message']['content'][m
[31m-            logger.info(f"Cloud {model_name} response: {len(content)} chars")[m
[31m-            return content[m
[31m-        else:[m
[31m-            logger.error(f"Cloud {model_name} error: {response.status_code} - {response.text}")[m
[31m-            return ""[m
[31m-            [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Cloud model error: {e}")[m
[31m-        return ""[m
[31m-[m
[31m-def handle_simple_query(text):[m
[31m-    """Обработка простых запросов без сложных моделей"""[m
[31m-    text_lower = text.lower().strip()[m
[31m-    [m
[31m-    # Приветствия[m
[31m-    if any(greeting in text_lower for greeting in ['привет', 'здравствуй', 'hi', 'hello', 'hey']):[m
[31m-        return "Привет! Я - II-Agent Pro. Чем могу помочь?"[m
[31m-    [m
[31m-    # Прощания[m
[31m-    if any(bye in text_lower for bye in ['пока', 'до свидания', 'bye', 'goodbye']):[m
[31m-        return "До свидания! Возвращайтесь, если будут вопросы."[m
[31m-    [m
[31m-    # Благодарности[m
[31m-    if any(thanks in text_lower for thanks in ['спасибо', 'благодарю', 'thanks', 'thank you']):[m
[31m-        return "Пожалуйста! Рад, что смог помочь."[m
[31m-    [m
[31m-    # Простые вычисления[m
[31m-    calc_pattern = r'^\s*(\d+(?:\.\d+)?)\s*([\+\-\*/])\s*(\d+(?:\.\d+)?)\s*$'[m
[31m-    match = re.match(calc_pattern, text)[m
[31m-    if match:[m
[31m-        num1, op, num2 = float(match.group(1)), match.group(2), float(match.group(3))[m
[31m-        try:[m
[31m-            if op == '+': result = num1 + num2[m
[31m-            elif op == '-': result = num1 - num2[m
[31m-            elif op == '*': result = num1 * num2[m
[31m-            elif op == '/': [m
[31m-                if num2 == 0: return "❌ Деление на ноль невозможно."[m
[31m-                result = num1 / num2[m
[31m-            else: return None[m
[31m-            return f"Результат: {result}"[m
[31m-        except:[m
[31m-            return "❌ Ошибка вычисления."[m
[31m-    [m
[31m-    # Информация о системе[m
[31m-    if 'информация' in text_lower and 'систем' in text_lower:[m
[31m-        metrics = get_system_metrics()[m
[31m-        return f"""[m
[31m-📊 Информация о системе:[m
[31m-- CPU: {metrics.get('cpu_percent', 'N/A')}%[m
[31m-- RAM: {metrics.get('memory_percent', 'N/A')}%[m
[31m-- Диск: {metrics.get('disk_percent', 'N/A')}%[m
[31m-- Время: {datetime.fromtimestamp(metrics.get('timestamp', time.time())).strftime('%Y-%m-%d %H:%M:%S')}[m
[31m-        """.strip()[m
[31m-    [m
[31m-    # Помощь[m
[31m-    if any(word in text_lower for word in ['помощь', 'help', 'что ты умеешь', 'функции']):[m
[31m-        return """[m
[31m-🤖 II-Agent Pro v4.0[m
[31m-- 🔍 Поиск в интернете (RAG)[m
[31m-- 💬 Ответы на вопросы[m
[31m-- 💻 Генерация и анализ кода[m
[31m-- 🖼️ Анализ изображений (LLaVA)[m
[31m-- 🎵 Поиск и скачивание музыки[m
[31m-- 📊 Системные метрики[m
[31m-- 🧠 Самообучение[m
[31m-- 📁 Работа с файлами[m
[31m-Просто задавайте вопросы![m
[31m-        """.strip()[m
[31m-    [m
[31m-    return None # Не обработано[m
[31m-# ==================== ПОГОДА ====================[m
[31m-def get_weather(city="Уфа"):[m
[31m-    """Получение погоды через OpenWeatherMap API"""[m
[31m-    api_key = "2ba311f07f7c0d9c80ae7078bb26e211"  # ТВОЙ КЛЮЧ[m
[31m-    if not api_key:[m
[31m-        logger.warning("OpenWeather API key not set")[m
[31m-        return "❌ API ключ погоды не настроен."[m
[31m-    [m
[31m-    try:[m
[31m-        # Получаем координаты города[m
[31m-        geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"[m
[31m-        geocode_response = requests.get(geocode_url, timeout=10)[m
[31m-        geocode_response.raise_for_status()[m
[31m-        [m
[31m-        location_data = geocode_response.json()[m
[31m-        if not location_data:[m
[31m-            return f"❌ Город '{city}' не найден."[m
[31m-        [m
[31m-        lat = location_data[0]['lat'][m
[31m-        lon = location_data[0]['lon'][m
[31m-        [m
[31m-        # Получаем погоду[m
[31m-        weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&lang=ru&units=metric"[m
[31m-        weather_response = requests.get(weather_url, timeout=10)[m
[31m-        weather_response.raise_for_status()[m
[31m-        [m
[31m-        data = weather_response.json()[m
[31m-        temp = data['main']['temp'][m
[31m-        feels_like = data['main']['feels_like'][m
[31m-        humidity = data['main']['humidity'][m
[31m-        description = data['weather'][0]['description'][m
[31m-        [m
[31m-        return f"""🌡️ Погода в {city}:[m
[31m-- Температура: {temp}°C (ощущается как {feels_like}°C)[m
[31m-- Влажность: {humidity}%[m
[31m-- Описание: {description.capitalize()}""".strip()[m
[31m-        [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Weather error: {e}")[m
[31m-        return f"❌ Ошибка получения погоды: {e}"[m
[31m-[m
[31m-[m
[31m-[m
[31m-def download_music(query):[m
[31m-    """Скачивание музыки с YouTube через yt-dlp"""[m
[31m-    try:[m
[31m-        # Поиск трека на YouTube[m
[31m-        ydl_opts = {[m
[31m-            'default_search': 'ytsearch',[m
[31m-            'max_downloads': 1,[m
[31m-            'format': 'bestaudio/best',[m
[31m-            'postprocessors': [{[m
[31m-                'key': 'FFmpegExtractAudio',[m
[31m-                'preferredcodec': 'mp3',[m
[31m-                'preferredquality': '192',[m
[31m-            }],[m
[31m-            'postprocessor_args': [[m
[31m-                '-ar', '44100'  # Установка частоты дискретизации[m
[31m-            ],[m
[31m-            'prefer_ffmpeg': True,[m
[31m-            'audioquality': '0',[m
[31m-            'extractaudio': True,[m
[31m-            'addmetadata': True,[m
[31m-            'embedthumbnail': True,[m
[31m-        }[m
[31m-        [m
[31m-        with yt_dlp.YoutubeDL(ydl_opts) as ydl:[m
[31m-            info = ydl.extract_info(f"ytsearch1:{query}", download=False)[m
[31m-            if not info or not info.get('entries'):[m
[31m-                return "❌ Не удалось найти музыку."[m
[31m-            [m
[31m-            track_info = info['entries'][0][m
[31m-            track_title = track_info.get('title', 'Неизвестный трек')[m
[31m-            track_url = track_info.get('webpage_url', '')[m
[31m-            [m
[31m-            # Скачивание[m
[31m-            ydl.download([track_url])[m
[31m-            [m
[31m-            # Предполагаем имя файла (yt-dlp может изменить его)[m
[31m-            filename = ydl.prepare_filename(track_info)[m
[31m-            base, ext = os.path.splitext(filename)[m
[31m-            mp3_filename = base + '.mp3'[m
[31m-            [m
[31m-            if os.path.exists(mp3_filename):[m
[31m-                # Генерация URL для скачивания (предполагаем, что файлы доступны через статический маршрут)[m
[31m-                download_url = f"/static/music/{os.path.basename(mp3_filename)}"[m
[31m-                return f"""[m
[31m-🎵 Трек найден: {track_title}[m
[31m-✅ Скачивание: {download_url}[m
[31m-                """.strip()[m
[31m-            else:[m
[31m-                return "❌ Не удалось сохранить трек."[m
[31m-                [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Music download error: {e}")[m
[31m-        return f"❌ Ошибка скачивания музыки: {e}"[m
[31m-[m
[31m-# ==================== RAG ПОИСК ====================[m
[31m-def rag_search_and_answer(query, model_name, use_cloud=False, cloud_model="auto"):[m
[31m-    """Основная функция RAG поиска и ответа"""[m
[31m-    logger.info(f"RAG search: {query[:50]}...")[m
[31m-    [m
[31m-    # 1. Поиск источников[m
[31m-    sources = search_multi_engine(query)[m
[31m-    if not sources:[m
[31m-        logger.warning("No sources found")[m
[31m-        return "❌ Не удалось найти информацию."[m
[31m-    [m
[31m-    # 2. Сортировка по приоритету[m
[31m-    sources.sort(key=lambda x: x.get('priority', 0), reverse=True)[m
[31m-    top_sources = sources[:3][m
[31m-    [m
[31m-    logger.info("Top sources:")[m
[31m-    for i, s in enumerate(top_sources, 1):[m
[31m-        logger.info(f" {i}. [{s.get('priority', 0)}] {s['url'][:60]}...")[m
[31m-    [m
[31m-    # 3. Парсинг содержимого[m
[31m-    parsed_sources = [][m
[31m-    for source in top_sources:[m
[31m-        # Если контента нет (только сниппет) — парсим страницу[m
[31m-        if 'content' not in source or not source['content']:[m
[31m-            articles = parse_url_deep(source['url'])[m
[31m-            if articles:[m
[31m-                source['content'] = articles[0]['content'][m
[31m-        if source.get('content') and len(source['content']) > 100:[m
[31m-            parsed_sources.append(source)[m
[31m-    [m
[31m-    if not parsed_sources:[m
[31m-        return "❌ Не удалось извлечь содержимое из источников."[m
[31m-    [m
[31m-    # 4. Агрегация через модель[m
[31m-    return aggregate_and_respond(parsed_sources, query, model_name, use_cloud, cloud_model)[m
[31m-[m
[31m-# ==================== АВТООПРЕДЕЛЕНИЕ ====================[m
[31m-def needs_web_search(text):[m
[31m-    """Улучшенное автоопределение необходимости поиска"""[m
[31m-    tl = text.lower().strip()[m
[31m-    [m
[31m-    # ==================== БЕЗ ИНТЕРНЕТА ====================[m
[31m-    # 1. Простые паттерны (приветствия, прощания)[m
[31m-    no_web_patterns = [[m
[31m-        r'^(привет|здравствуй|hi|hello|hey|добрый день)[\s\!\?]*$',[m
[31m-        r'^(пока|до свидания|bye|goodbye)[\s\!\?]*$',[m
[31m-        r'^(спасибо|благодарю|thanks|thank you)[\s\!\?]*$',[m
[31m-        r'^(как дела|как ты|что делаешь)[\?]?$', # Общие фразы[m
[31m-        r'^\d+\s*[\+\-\*/]\s*\d+', # Простые вычисления[m
[31m-    ][m
[31m-    for pattern in no_web_patterns:[m
[31m-        if re.match(pattern, tl):[m
[31m-            logger.info("No web: simple greeting/math")[m
[31m-            return False[m
[31m-[m
[31m-    # 2. Логические задачи и загадки[m
[31m-    logic_keywords = ['загадка', 'ребус', 'логическая задача', 'какое слово', 'что общего'][m
[31m-    if any(kw in tl for kw in logic_keywords):[m
[31m-        logger.info("No web: logic/riddle")[m
[31m-        return False[m
[31m-    [m
[31m-    # 3. Математика и физика (если НЕ про курсы валют)[m
[31m-    math_keywords = ['вычисли', 'рассчита', 'реши уравнение', 'найди корни', 'производная', 'интеграл', 'докажи'][m
[31m-    if any(kw in tl for kw in math_keywords):[m
[31m-        # НО курсы валют — это интернет[m
[31m-        if not any(word in tl for word in ['курс', 'цена', 'стоимость']):[m
[31m-            logger.info("No web: math/physics calculation")[m
[31m-            return False[m
[31m-[m
[31m-    # 4. Философия и рассуждения (без фактов)[m
[31m-    philosophy_keywords = ['этика', 'мораль', 'философия', 'смысл жизни', 'что лучше', 'твоё мнение', 'как ты думаешь'][m
[31m-    if any(kw in tl for kw in philosophy_keywords):[m
[31m-        logger.info("No web: philosophical question")[m
[31m-        return False[m
[31m-[m
[31m-    # ==================== ИНТЕРНЕТ ====================[m
[31m-    # 1. Паттерны, явно требующие интернет[m
[31m-    web_patterns = [[m
[31m-        (r'(вчера|позавчера|недавно|только что).*?(произош|случил|стал)', "недавние события"),[m
[31m-        (r'погода\s+(в|сегодня|завтра)', "погода"),[m
[31m-        (r'(цена|стоимость|курс|котировк)', "финансы"),[m
[31m-        (r'https?://', "прямая ссылка"),[m
[31m-        (r'(выполни|запусти)\s+(код|скрипт|python)', "выполнение кода"),[m
[31m-    ][m
[31m-    for pattern, reason in web_patterns:[m
[31m-        if re.search(pattern, tl):[m
[31m-            logger.info(f"Web needed: {reason}")[m
[31m-            return True[m
[31m-[m
[31m-    # 2. Конкретные годы (исторические факты)[m
[31m-    if re.search(r'\d{4}\s*(год|г\.)', tl):[m
[31m-        logger.info("Web needed: specific year")[m
[31m-        return True[m
[31m-[m
[31m-    # 3. Даты[m
[31m-    date_patterns = [r'\d{2}\.\d{2}\.\d{4}', r'\d{4}-\d{2}-\d{2}'][m
[31m-    for pattern in date_patterns:[m
[31m-        if re.search(pattern, tl):[m
[31m-            logger.info("Web needed: specific date")[m
[31m-            return True[m
[31m-[m
[31m-    # 4. Новости и события[m
[31m-    news_keywords = ['новости', 'события', 'что произошло', 'последние'][m
[31m-    if any(kw in tl for kw in news_keywords):[m
[31m-        # Но не если спрашивают про 2023, 2022 и т.д. - это может быть в базе знаний[m
[31m-        if not any(year in tl for year in ['2025', '2024', '2023']):[m
[31m-            logger.info("Web needed: recent news")[m
[31m-            return True[m
[31m-[m
[31m-    # 5. Инструкции и руководства[m
[31m-    query_lower = tl[m
[31m-    if 'как' in query_lower:[m
[31m-        action_words = ['установить', 'настроить', 'запустить', 'использовать', 'создать', 'сделать'][m
[31m-        if any(word in query_lower for word in action_words):[m
[31m-            # Если явно не запрошено "руководство" или "инструкция", добавляем[m
[31m-            if 'инструкция' not in query_lower and 'руководство' not in query_lower:[m
[31m-                logger.info("Web needed: instruction/guide")[m
[31m-                return True[m
[31m-[m
[31m-    # 6. Сравнения[m
[31m-    if ' vs ' in query_lower or (' или ' in query_lower and len(query_lower.split()) <= 6):[m
[31m-         logger.info("Web needed: comparison")[m
[31m-         return True[m
[31m-[m
[31m-    # 7. Поиск файлов, музыки, видео[m
[31m-    media_keywords = ['скачай', 'музык', 'трек', 'песня', 'видео', 'фильм'][m
[31m-    if any(kw in tl for kw in media_keywords):[m
[31m-        logger.info("Web needed: media download")[m
[31m-        return True[m
[31m-[m
[31m-    # По умолчанию — нужен интернет для получения актуальной информации[m
[31m-    logger.info("Web needed: default")[m
[31m-    return True[m
[31m-[m
[31m-# ==================== STREAMING ====================[m
[31m-async def stream_response(text, model_name, use_web=True, use_cloud=False, cloud_model="auto"):[m
[31m-    """Основной обработчик запросов с streaming"""[m
[31m-    try:[m
[31m-        yield "data: " + json.dumps({"status": "🔍 Анализ...", "type": "info"}) + "\n"[m
[31m-[m
[31m-        # 1. Простые запросы[m
[31m-        simple_answer = handle_simple_query(text)[m
[31m-        if simple_answer:[m
[31m-            logger.info("Simple query")[m
[31m-            yield "data: " + json.dumps({"status": "✓ Готово", "type": "success"}) + "\n"[m
[31m-            yield "data: " + json.dumps({"answer": simple_answer}) + "\n"[m
[31m-            return[m
[31m-[m
[31m-        # 2. Если пользователь отключил интернет[m
[31m-        if not use_web:[m
[31m-            logger.info("User disabled web")[m
[31m-            yield "data: " + json.dumps({"status": "💻 Локальный режим (отключён интернет)", "type": "info"}) + "\n"[m
[31m-            result = call_model(text, model_name)[m
[31m-            yield "data: " + json.dumps({"status": "✓ Готово", "type": "success"}) + "\n"[m
[31m-            yield "data: " + json.dumps({"answer": result}) + "\n"[m
[31m-            return[m
[31m-[m
[31m-        # 3. Автоопределение необходимости интернета[m
[31m-        auto_needs_web = needs_web_search(text)[m
[31m-        if not auto_needs_web:[m
[31m-            logger.info("Auto: web not needed")[m
[31m-            yield "data: " + json.dumps({"status": "💻 Локальный режим (по автоопределению)", "type": "info"}) + "\n"[m
[31m-            result = call_model(text, model_name)[m
[31m-            yield "data: " + json.dumps({"status": "✓ Готово", "type": "success"}) + "\n"[m
[31m-            yield "data: " + json.dumps({"answer": result}) + "\n"[m
[31m-            return[m
[31m-[m
[31m-        # 4. Интернет-режим[m
[31m-        logger.info("Web mode: RAG")[m
[31m-        yield "data: " + json.dumps({"status": "🌐 Поиск в интернете", "type": "info"}) + "\n"[m
[31m-        [m
[31m-        validated_urls = extract_and_validate_urls(text)[m
[31m-        if validated_urls:[m
[31m-            intent = "url"[m
[31m-        else:[m
[31m-            tl = text.lower()[m
[31m-            if "погода" in tl:[m
[31m-                intent = "weather"[m
[31m-            elif any(w in tl for w in ['скачай', 'музык', 'трек']):[m
[31m-                intent = "music"[m
[31m-            else:[m
[31m-                intent = "rag"[m
[31m-[m
[31m-        logger.info(f"Intent: {intent}")[m
[31m-        if intent == "url":[m
[31m-            if not validated_urls:[m
[31m-                result = "❌ Не найдено валидных URL"[m
[31m-            else:[m
[31m-                yield "data: " + json.dumps({"status": f"📥 Парсинг {len(validated_urls)} URL...", "type": "info"}) + "\n"[m
[31m-                sources = [][m
[31m-                for i, url in enumerate(validated_urls, 1):[m
[31m-                    yield "data: " + json.dumps({"status": f"🌐 {i}/{len(validated_urls)}: {url[:50]}...", "type": "info"}) + "\n"[m
[31m-                    articles = parse_url_deep(url)[m
[31m-                    if articles:[m
[31m-                        for article in articles[:3]: # Берём до 3 статей с одной страницы[m
[31m-                            sources.append({[m
[31m-                                'url': url,[m
[31m-                                'title': article['title'],[m
[31m-                                'content': article['content'][m
[31m-                            })[m
[31m-                [m
[31m-                if not sources:[m
[31m-                    result = "❌ Не удалось извлечь содержимое"[m
[31m-                else:[m
[31m-                    yield "data: " + json.dumps({"status": f"🧠 Анализ ({model_name})...", "type": "info"}) + "\n"[m
[31m-                    task_description = "Пользователь предоставил веб-ссылки. Проанализируй содержимое."[m
[31m-                    result = aggregate_and_respond(sources, text, model_name, use_cloud, cloud_model)[m
[31m-[m
[31m-        elif intent == "weather":[m
[31m-            city_match = re.search(r'в\s+([а-яА-Яa-zA-Z\-]+)', text, re.I)[m
[31m-            city = city_match.group(1) if city_match else "Москва"[m
[31m-            yield "data: " + json.dumps({"status": f"🌦 {city}...", "type": "info"}) + "\n"[m
[31m-            result = get_weather(city)[m
[31m-[m
[31m-        elif intent == "music":[m
[31m-            query = re.sub(r'(скачай|музык)', '', text, flags=re.I).strip()[m
[31m-            yield "data: " + json.dumps({"status": f"🎵 {query}...", "type": "info"}) + "\n"[m
[31m-            result = download_music(query)[m
[31m-[m
[31m-        else: # RAG[m
[31m-            yield "data: " + json.dumps({"status": "🔎 Поиск...", "type": "info"}) + "\n"[m
[31m-            yield "data: " + json.dumps({"status": "📥 ТОП-3...", "type": "info"}) + "\n"[m
[31m-            yield "data: " + json.dumps({"status": "📄 Парсинг...", "type": "info"}) + "\n"[m
[31m-            if use_cloud:[m
[31m-                yield "data: " + json.dumps({"status": f"☁️ {cloud_model}...", "type": "info"}) + "\n"[m
[31m-            else:[m
[31m-                yield "data: " + json.dumps({"status": f"🧠 {model_name}...", "type": "info"}) + "\n"[m
[31m-            result = rag_search_and_answer(text, model_name, use_cloud, cloud_model)[m
[31m-        [m
[31m-        yield "data: " + json.dumps({"status": "✓ Готово", "type": "success"}) + "\n"[m
[31m-        yield "data: " + json.dumps({"answer": result}) + "\n"[m
[31m-        [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Stream error: {e}")[m
[31m-        yield "data: " + json.dumps({"answer": f"❌ Ошибка: {str(e)}"}) + "\n"[m
[31m-[m
[31m-# ==================== FASTAPI ПРИЛОЖЕНИЕ ====================[m
[31m-app = FastAPI(title="II-Agent Pro API", version="4.0")[m
[31m-[m
[31m-# CORS middleware[m
[31m-from fastapi.middleware.cors import CORSMiddleware[m
[31m-app.add_middleware([m
[31m-    CORSMiddleware,[m
[31m-    allow_origins=["*"],[m
[31m-    allow_credentials=True,[m
[31m-    allow_methods=["*"],[m
[31m-    allow_headers=["*"],[m
[31m-)[m
[31m-[m
[31m-# ==================== API ENDPOINTS ====================[m
[31m-[m
[31m-@app.get("/")[m
[31m-async def root():[m
[31m-    """Корневой эндпоинт"""[m
[31m-    return {[m
[31m-        "name": "II-Agent Pro API",[m
[31m-        "version": "4.0",[m
[31m-        "status": "running",[m
[31m-        "chromadb": CHROMADB_AVAILABLE,[m
[31m-        "gpu": HAS_GPU[m
[31m-    }[m
[31m-[m
[31m-@app.get("/health")[m
[31m-async def health_check():[m
[31m-    """Проверка здоровья системы"""[m
[31m-    return {[m
[31m-        "status": "healthy",[m
[31m-        "chromadb": CHROMADB_AVAILABLE,[m
[31m-        "gpu": HAS_GPU,[m
[31m-        "timestamp": datetime.now(pytz.UTC).isoformat()[m
[31m-    }[m
[31m-[m
[31m-@app.get("/stats")[m
[31m-async def get_stats():[m
[31m-    """Статистика системы"""[m
[31m-    try:[m
[31m-        db_stats = get_db_stats()[m
[31m-        system_metrics = get_system_metrics()[m
[31m-        return {[m
[31m-            **db_stats,[m
[31m-            **system_metrics,[m
[31m-            "chromadb_available": CHROMADB_AVAILABLE,[m
[31m-            "gpu_available": HAS_GPU[m
[31m-        }[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Stats error: {e}")[m
[31m-        return {"error": str(e)}[m
[31m-[m
[31m-@app.post("/ask")[m
[31m-async def ask_endpoint(request: Request):[m
[31m-    """Основной эндпоинт с streaming"""[m
[31m-    try:[m
[31m-        data = await request.json()[m
[31m-        query = data.get("query", "")[m
[31m-        model_name = data.get("model", "qwen2.5:7b-instruct-q4_K_M")[m
[31m-        use_web = data.get("use_web", True)[m
[31m-        use_cloud = data.get("use_cloud", False)[m
[31m-        cloud_model = data.get("cloud_model", "auto")[m
[31m-        [m
[31m-        if not query:[m
[31m-            raise HTTPException(status_code=400, detail="Query is required")[m
[31m-        [m
[31m-        logger.info(f"Query: {query[:50]}... | Model: {model_name} | Web: {use_web}")[m
[31m-        [m
[31m-        return StreamingResponse([m
[31m-            stream_response(query, model_name, use_web, use_cloud, cloud_model),[m
[31m-            media_type="text/event-stream",[m
[31m-            headers={[m
[31m-                "Cache-Control": "no-cache",[m
[31m-                "Connection": "keep-alive",[m
[31m-                "X-Accel-Buffering": "no"[m
[31m-            }[m
[31m-        )[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Ask endpoint error: {e}")[m
[31m-        raise HTTPException(status_code=500, detail=str(e))[m
[31m-[m
[31m-@app.post("/chat")[m
[31m-async def chat_endpoint(request: Request):[m
[31m-    """Альтернативный эндпоинт (без streaming)"""[m
[31m-    try:[m
[31m-        data = await request.json()[m
[31m-        query = data.get("query", "")[m
[31m-        model_name = data.get("model", "qwen2.5:7b-instruct-q4_K_M")[m
[31m-        use_web = data.get("use_web", True)[m
[31m-        [m
[31m-        if not query:[m
[31m-            raise HTTPException(status_code=400, detail="Query is required")[m
[31m-        [m
[31m-        # Простая обработка[m
[31m-        simple_answer = handle_simple_query(query)[m
[31m-        if simple_answer:[m
[31m-            return {"answer": simple_answer, "model": "simple"}[m
[31m-        [m
[31m-        # Автоопределение[m
[31m-        if not use_web or not needs_web_search(query):[m
[31m-            response = call_model(query, model_name)[m
[31m-            return {"answer": response, "model": model_name, "web_used": False}[m
[31m-        [m
[31m-        # RAG[m
[31m-        response = rag_search_and_answer(query, model_name)[m
[31m-        return {"answer": response, "model": model_name, "web_used": True}[m
[31m-        [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Chat endpoint error: {e}")[m
[31m-        raise HTTPException(status_code=500, detail=str(e))[m
[31m-[m
[31m-@app.post("/upload_file")[m
[31m-async def upload_file_endpoint(file: UploadFile = File(...)):[m
[31m-    """Загрузка файлов"""[m
[31m-    try:[m
[31m-        if file.size > MAX_FILE_SIZE:[m
[31m-            raise HTTPException(status_code=400, detail="File too large")[m
[31m-        [m
[31m-        # Сохранение файла[m
[31m-        filename = f"{int(time.time())}_{file.filename}"[m
[31m-        filepath = Path(f"/app/data/uploads/{filename}")[m
[31m-        filepath.parent.mkdir(parents=True, exist_ok=True)[m
[31m-        [m
[31m-        async with aiofiles.open(filepath, 'wb') as f:[m
[31m-            content = await file.read()[m
[31m-            await f.write(content)[m
[31m-        [m
[31m-        logger.info(f"File uploaded: {filename}")[m
[31m-        return {[m
[31m-            "filename": filename,[m
[31m-            "size": len(content),[m
[31m-            "path": str(filepath)[m
[31m-        }[m
[31m-        [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Upload error: {e}")[m
[31m-        raise HTTPException(status_code=500, detail=str(e))[m
[31m-[m
[31m-@app.get("/history")[m
[31m-async def get_history(user_id: str = "default", limit: int = 10):[m
[31m-    """История диалогов"""[m
[31m-    try:[m
[31m-        history = get_conversation_history(user_id, limit)[m
[31m-        return {"history": history, "count": len(history)}[m
[31m-    except Exception as e:[m
[31m-        logger.error(f"History error: {e}")[m
[31m-        raise HTTPException(status_code=500, detail=str(e))[m
[31m-[m
[31m-@app.post("/rate")[m
[31m-async def rate_conversation(request: Request):[m
[31m-    """Оценка ответа"""[m
[31m-    try:[m
[31m-        data = await request.json()[m
[31m-        conversation_id = data.get("id")[m
[31m-        rating = data.get("rating", 0)[m
[31m-        [m
[31m-        if not conversation_id:[m
[31m-            raise HTTPException(status_code=400, detail="ID required")[m
[31m-        [m
[31m-        conn = sqlite3.connect('ii_agent.db')[m
[31m-        c = conn.cursor()[m
[31m-        c.execute("UPDATE conversations SET rating=? WHERE id=?", (rating, conversation_id))[m
[31m-        conn.commit()[m
[31m-        conn.close()[m
[31m-        [m
[31m-        return {"status": "ok", "id": conversation_id, "rating": rating}[m
[31m-        [m
[31m-    except Exception as e:[m
[31m-        logger.error(f"Rate error: {e}")[m
[31m-        raise HTTPException(status_code=500, detail=str(e))[m
[31m-[m
[31m-# ==================== TESTING ENDPOINTS ====================[m
[31m-[m
[31m-@app.post("/api/test/run")[m
[31m-async def run_tests():[m
[31m-    """Запуск всех тестов"""[m
[31m-    result = test_system.run_all_tests()[m
[31m-    return result[m
[31m-[m
[31m-@app.get("/api/test/report")[m
[31m-async def get_test_report():[m
[31m-    """Получить отчёт о тестировании"""[m
[31m-    report = test_system.generate_test_report()[m
[31m-    return {"report": report}[m
[31m-[m
[31m-@app.get("/api/test/history")[m
[31m-async def get_test_history(limit: int = 10):[m
[31m-    """История тестирования"""[m
[31m-    history = test_system.get_test_history(limit)[m
[31m-    return {"history": history}[m
[31m-[m
[31m-# ==================== BACKUP ENDPOINTS ====================[m
[31m-[m
[31m-@app.post("/api/backup/create")[m
[31m-async def create_backup(message: str = "Manual backup", critical: bool = False):[m
[31m-    """Создание бэкапа"""[m
[31m-    result = backup_system.create_backup([m
[31m-        message=message,[m
[31m-        author="User",[m
[31m-        critical=critical[m
[31m-    )[m
[31m-    return result[m
[31m-[m
[31m-@app.post("/api/backup/rollback")[m
[31m-async def rollback_backup(tag_name: str = None, confirm: bool = False):[m
[31m-    """Откат к бэкапу"""[m
[31m-    result = backup_system.rollback(tag_name=tag_name, confirm=confirm)[m
[31m-    return result[m
[31m-[m
[31m-@app.get("/api/backup/list")[m
[31m-async def list_backups(limit: int = 10):[m
[31m-    """Список бэкапов"""[m
[31m-    backups = backup_system.list_backups(limit=limit)[m
[31m-    return {"backups": backups}[m
[31m-[m
[31m-@app.get("/api/backup/diff/{tag_name}")[m
[31m-async def get_backup_diff(tag_name: str):[m
[31m-    """Просмотр изменений"""[m
[31m-    result = backup_system.get_diff(tag_name)[m
[31m-    return result[m
[31m-[m
[31m-# ==================== MODEL HIERARCHY ENDPOINTS ====================[m
[31m-[m
[31m-@app.post("/api/model/call")[m
[31m-async def call_model_endpoint(prompt: str, level: str = "junior"):[m
[31m-    """Вызов модели определённого уровня"""[m
[31m-    result = model_hierarchy.call_model(prompt, level=level)[m
[31m-    return result[m
[31m-[m
[31m-@app.post("/api/model/escalate")[m
[31m-async def escalate_to_senior(prompt: str, current_level: str = "junior", reason: str = ""):[m
[31m-    """Эскалация к более умной модели"""[m
[31m-    result = model_hierarchy.escalate(prompt, current_level, reason)[m
[31m-    return result[m
[31m-[m
[31m-@app.get("/api/model/stats")[m
[31m-async def get_escalation_stats():[m
[31m-    """Статистика эскалаций"""[m
[31m-    stats = model_hierarchy.get_escalation_stats()[m
[31m-    return stats[m
[31m-[m
[31m-# ==================== ЗАПУСК ====================[m
[31m-if __name__ == "__main__":[m
[31m-    import uvicorn[m
[31m-    logger.info("🚀 Starting II-Agent Pro API...")[m
[31m-    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")[m
\ No newline at end of file[m
