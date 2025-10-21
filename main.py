from dotenv import load_dotenv
import os
from pathlib import Path

import asyncio
import aiofiles
from gigachat_api import GigaChatAPI
import logging
import requests
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import hashlib
import json
import time
import re
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import GPUtil
import psutil
import subprocess
import yt_dlp
import sqlite3
import threading
from queue import Queue
import ast
import urllib.parse
from duckduckgo_search import DDGS  # Fallback only
from bs4 import BeautifulSoup
import wikipedia
import base64
import pytz

# ==================== NEW SYSTEMS ====================
from test_system import test_system
from backup_system import backup_system
from model_hierarchy import model_hierarchy

# ==================== LOGGING SETUP (FIXED!) ====================
log_dir = Path("/app/logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'ii_agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


# ==================== PERFORMANCE MODULES ====================
from cache_manager import CacheManager
from async_scraper import AsyncScraper

logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f'✅ Loaded .env from {env_path}')
else:
    logger.warning('⚠️ .env file not found')

# Initialize performance modules
cache_manager = CacheManager(db_path='data/cache.db', ttl=3600)
async_scraper = AsyncScraper(timeout=10, max_concurrent=5)
logger.info('? Performance modules initialized')


# Константы
MODEL_TIMEOUT = 300
MAX_FILE_SIZE = 10 * 1024 * 1024
CHROMA_DB_PATH = "/app/data/chroma_db"
BACKUP_DIR = Path("/app/data/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_API_URL = "http://host.docker.internal:11434"

# Проверка GPU
try:
    gpus = GPUtil.getGPUs()
    HAS_GPU = len(gpus) > 0
    if HAS_GPU:
        logger.info(f"GPU detected: {gpus[0].name}, VRAM: {gpus[0].memoryTotal}MB")
    else:
        logger.warning("GPU not detected")
except:
    HAS_GPU = False
    logger.warning("GPU detection failed")

# Проверка ChromaDB
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embedder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    CHROMADB_AVAILABLE = True
    logger.info("✅ ChromaDB and SentenceTransformer initialized")
except Exception as e:
    CHROMADB_AVAILABLE = False
    logger.warning(f"⚠️ ChromaDB not available: {e}")

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    """Инициализация SQLite базы данных"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  query TEXT,
                  response TEXT,
                  sources TEXT,
                  model_used TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  rating INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS knowledge_base
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  topic TEXT,
                  content TEXT,
                  source TEXT,
                  confidence REAL DEFAULT 0.5,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def save_conversation(query, response, sources, model_used, user_id="default"):
    """Сохранение диалога в базу"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    c = conn.cursor()
    c.execute("INSERT INTO conversations (user_id, query, response, sources, model_used) VALUES (?, ?, ?, ?, ?)",
              (user_id, query, response, json.dumps(sources), model_used))
    conn.commit()
    conversation_id = c.lastrowid
    conn.close()
    return conversation_id

def get_db_cursor():
    """Получить курсор БД"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    return conn.cursor()

def add_knowledge(topic, content, source, confidence=0.8):
    """Добавление знаний в базу"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    c = conn.cursor()
    c.execute("INSERT INTO knowledge_base (topic, content, source, confidence) VALUES (?, ?, ?, ?)",
              (topic, content, source, confidence))
    conn.commit()
    conn.close()

def search_knowledge_base(query):
    """Поиск в базе знаний"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    c = conn.cursor()
    c.execute("SELECT topic, content, source, confidence FROM knowledge_base WHERE topic LIKE ? OR content LIKE ? ORDER BY confidence DESC LIMIT 5",
              (f"%{query}%", f"%{query}%"))
    results = c.fetchall()
    conn.close()
    return results

def get_conversation_history(user_id="default", limit=50):
    """Получить историю диалогов"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    c = conn.cursor()
    c.execute("SELECT query, response, timestamp FROM conversations WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
              (user_id, limit))
    history = c.fetchall()
    conn.close()
    return history

def get_db_stats():
    """Статистика БД"""
    conn = sqlite3.connect('/app/data/ii_agent.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM conversations")
    total_conversations = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM knowledge_base")
    total_knowledge = c.fetchone()[0]
    
    conn.close()
    
    return {
        "conversations": total_conversations,
        "knowledge_items": total_knowledge
    }

# Инициализация БД
init_db()
# ==================== WEB ПОИСК ====================
def search_web(query, max_results=5):
    """Поиск через Google Custom Search Engine"""
    try:
        google_key = os.getenv('GOOGLE_API_KEY')
        google_cx = os.getenv('GOOGLE_CSE_CX')
        
        if not google_key or not google_cx:
            logger.error('❌ Google API keys not found in .env')
            return []
        
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {
            'key': google_key,
            'cx': google_cx,
            'q': query,
            'num': max_results
        }
        
        # Check cache first
        cache_key = f"{query}_{max_results}"
        cached_results = cache_manager.get(cache_key, 'google_cse')
        if cached_results:
            logger.info(f'🎯 Cache HIT for Google CSE: {query[:50]}...')
            return cached_results

        logger.info(f'🔍 Google CSE search: {query}')
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get('items', []):
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', '')
                })
            # Save to cache
            if results:
                cache_manager.set(cache_key, results, 'google_cse', ttl=3600)
                logger.info(f'💾 Cached {len(results)} results')
            
            logger.info(f'✅ Found {len(results)} results from Google CSE')
            return results
        else:
            logger.error(f'❌ Google CSE error: {response.status_code}')
            return []
            
    except Exception as e:
        logger.error(f'❌ Search error: {e}')
        return []


def get_weather(city='Уфа'):
    """Получение точного прогноза погоды через OpenWeatherMap API"""
    try:
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if not api_key:
            logger.warning('OpenWeatherMap API key not found')
            return None
        
        url = f'http://api.openweathermap.org/data/2.5/weather'
        params = {
            'q': city,
            'appid': api_key,
            'units': 'metric',
            'lang': 'ru'
        }
        
        logger.info(f'🌤️ OpenWeatherMap API: {city}')
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            weather_info = {
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'description': data['weather'][0]['description'],
                'humidity': data['main']['humidity'],
                'wind_speed': data['wind']['speed'],
                'city': data['name']
            }
            logger.info(f'✅ Weather data received for {city}')
            return weather_info
        else:
            logger.error(f'❌ OpenWeatherMap error: {response.status_code}')
            return None
    except Exception as e:
        logger.error(f'❌ Weather API error: {e}')
        return None


def scrape_url(url, max_length=1500):
    """
    Улучшенное извлечение текста со страницы с фокусом на основной контент
    
    Args:
        url: URL страницы
        max_length: Максимальная длина текста (по умолчанию 1500)
    
    Returns:
        str: Извлечённый текст или пустая строка при ошибке
    """
    try:
        logger.info(f'🌐 Scraping URL: {url}')
        
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
        })
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logger.warning(f'⚠️ HTTP {response.status_code} for {url}')
            return ""
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Удаляем ненужные элементы
        for script in soup(['script', 'style', 'nav', 'footer', 'aside', 'header', 'iframe', 'noscript', 'form']):
            script.decompose()
        
        # Ищем основной контент (приоритетные селекторы)
        content = None
        selectors = [
            'article', 
            'main', 
            '.article-body',
            '.article-content', 
            '.news-content', 
            '.post-content',
            '.entry-content',
            '[itemprop="articleBody"]'
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                logger.info(f'✅ Found content with: {selector}')
                break
        
        if content:
            text = content.get_text(separator=' ', strip=True)
        else:
            # Fallback: все параграфы
            paragraphs = soup.find_all('p')
            text = ' '.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
            logger.info(f'✅ Extracted {len(paragraphs)} paragraphs as fallback')
        
        # Очистка от лишних пробелов
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Обрезаем до нужной длины
        if len(text) > max_length:
            text = text[:max_length] + '...'
        
        logger.info(f'✅ Scraped {len(text)} chars from {url}')
        return text
        
    except requests.Timeout:
        logger.error(f'⏱️ Timeout scraping {url}')
        return ""
    except Exception as e:
        logger.error(f'❌ Scraping error for {url}: {str(e)[:100]}')
        return ""


def detect_query_type(query):
    """
    Определяет тип запроса для правильной обработки контента
    
    Args:
        query: Текст запроса пользователя
    
    Returns:
        str: Тип запроса ('weather', 'news', 'tutorial', 'general')
    """
    query_lower = query.lower()
    
    # Погода
    weather_keywords = ['погода', 'температур', 'градус', 'прогноз', 'климат', 'weather', 'осадки', 'ветер', 'дожд', 'снег']
    if any(kw in query_lower for kw in weather_keywords):
        logger.info('🌤️ Query type: WEATHER')
        return 'weather'
    
    # Новости
    news_keywords = ['новост', 'события', 'произошло', 'случилось', 'news', 'сегодня', 'вчера', 'главные']
    if any(kw in query_lower for kw in news_keywords):
        logger.info('📰 Query type: NEWS')
        return 'news'
    
    # Инструкции/гайды
    tutorial_keywords = ['как ', 'инструкции', 'способ', 'метод', 'гайд', 'tutorial', 'пошаг', 'научи', 'объясни как']
    if any(kw in query_lower for kw in tutorial_keywords):
        logger.info('📚 Query type: TUTORIAL')
        return 'tutorial'
    
    # Общие вопросы (по умолчанию)
    logger.info('💬 Query type: GENERAL')
    return 'general'

# ==================== OLLAMA ВЗАИМОДЕЙСТВИЕ ====================


def filter_chinese_characters(text: str) -> str:
    if not text:
        return text
    # иапазоны для китайских символов  пунктуации
    chinese_ranges = [
        (0x4E00, 0x9FFF),   # сновные иероглифы
        (0x3400, 0x4DBF),   # асширение A
        (0x20000, 0x2A6DF), # асширение B
        (0x3000, 0x303F),   # итайская пунктуация
        (0xFF00, 0xFFEF)    # олноширинные символы
    ]
    filtered_chars = []
    for char in text:
        char_code = ord(char)
        is_chinese = any(start <= char_code <= end for start, end in chinese_ranges)
        if not is_chinese:
            filtered_chars.append(char)
    return ''.join(filtered_chars).strip()



def query_ai(prompt, provider='ollama', model='qwen2.5:7b-instruct-q5_K_M', temperature=0.7):
    """????????????? ????? AI: Ollama, Groq ??? GigaChat"""
    try:
        if provider == 'ollama':
            return query_ollama(prompt, model, temperature)
        
        elif provider == 'groq':
            from cloud_models import GroqAPI
            groq = GroqAPI()
            return groq.chat(prompt, model='llama-3.3-70b-versatile')
        
        elif provider == 'gigachat':
            from cloud_models import GigaChatAPI
            gigachat = GigaChatAPI()
            return gigachat.chat(prompt, model='GigaChat-Pro')
        
        else:
            logger.error(f'Unknown provider: {provider}')
            return query_ollama(prompt, model, temperature)
    
    except Exception as e:
        logger.error(f'AI query error ({provider}): {e}')
        return query_ollama(prompt, model, temperature)


def query_ollama(prompt, model="qwen2.5:7b-instruct-q5_K_M", temperature=0.7):
    """Запрос к Ollama LLM"""
    try:
        logger.info(f"🔍 Sending to Ollama: model={model}")
        
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "stream": False
            },
            timeout=MODEL_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            logger.error(f"Ollama API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Ollama query error: {e}")
        return None

async def stream_ollama(prompt, model="qwen2.5:7b-instruct-q5_K_M", temperature=0.7):
    """Стриминг ответа от Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "stream": True
            },
            stream=True,
            timeout=MODEL_TIMEOUT
        )
        
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    yield data["response"]
                    
    except Exception as e:
        logger.error(f"Ollama streaming error: {e}")
        yield f"Error: {str(e)}"

# ==================== АДМИНКА API ====================

app = FastAPI(
    title="II-Agent Pro API",
    description="Локальный AI-агент с саморазвитием",
    version="5.0"
)


@app.get("/api/admin/models")
async def get_ollama_models():
    """Получить список всех моделей Ollama"""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        models_data = response.json()
        models = models_data.get("models", [])
        
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        
        for model in models:
            model_name = model.get("name", "")
            c.execute("SELECT COUNT(*) FROM conversations WHERE model_used = ?", (model_name,))
            usage_count = c.fetchone()[0]
            model["usage_count"] = usage_count
            
        conn.close()
        
        return {"models": models, "status": "success"}
        
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return {"error": str(e), "models": []}

@app.post("/api/admin/models/pull")
async def pull_ollama_model(request: Request):
    """Загрузить новую модель"""
    try:
        data = await request.json()
        model_name = data.get("model")
        
        if not model_name:
            raise HTTPException(status_code=400, detail="Model name required")
        
        response = requests.post(
            f"{OLLAMA_API_URL}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=3600
        )
        
        async def stream_progress():
            for line in response.iter_lines():
                if line:
                    yield f"data: {line.decode()}\n\n"
                    await asyncio.sleep(0.1)
        
        return StreamingResponse(stream_progress(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Error pulling model: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/api/admin/models/{model_name}")
async def delete_ollama_model(model_name: str):
    """Удалить модель"""
    try:
        response = requests.delete(
            f"{OLLAMA_API_URL}/api/delete",
            json={"name": model_name},
            timeout=30
        )
        
        if response.status_code == 200:
            return {"status": "success", "message": f"Model {model_name} deleted"}
        else:
            return {"status": "error", "message": f"Failed to delete: {response.text}"}
            
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        return {"error": str(e)}

@app.get("/api/admin/system/stats")
async def get_system_stats():
    """Получить системную статистику"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        ram = psutil.virtual_memory()
        ram_total = ram.total / (1024**3)
        ram_used = ram.used / (1024**3)
        ram_percent = ram.percent
        
        gpu_stats = []
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_stats.append({
                    "name": gpu.name,
                    "load": round(gpu.load * 100, 1),
                    "memory_used": gpu.memoryUsed,
                    "memory_total": gpu.memoryTotal,
                    "temperature": gpu.temperature
                })
        except:
            gpu_stats = []
        
        disk = psutil.disk_usage('/app/data')
        disk_total = disk.total / (1024**3)
        disk_used = disk.used / (1024**3)
        disk_percent = disk.percent
        
        return {
            "cpu": {"percent": round(cpu_percent, 1), "count": cpu_count},
            "ram": {"total_gb": round(ram_total, 2), "used_gb": round(ram_used, 2), "percent": round(ram_percent, 1)},
            "gpu": gpu_stats,
            "disk": {"total_gb": round(disk_total, 2), "used_gb": round(disk_used, 2), "percent": round(disk_percent, 1)},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {"error": str(e)}

@app.get("/api/admin/logs")
async def get_logs(level: str = "INFO", limit: int = 100):
    """Получить логи системы"""
    try:
        log_file = Path("/app/logs/ii_agent.log")
        
        if not log_file.exists():
            return {"logs": [], "message": "Log file not found"}
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if level != "ALL":
            filtered = [line for line in lines if level in line]
        else:
            filtered = lines
        
        return {"logs": filtered[-limit:], "total": len(filtered), "level": level}
        
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return {"error": str(e), "logs": []}

@app.post("/api/admin/settings")
async def update_settings(request: Request):
    """Обновить настройки системы"""
    try:
        settings = await request.json()
        config_file = Path("/app/data/settings.json")
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Settings updated: {settings}")
        return {"status": "success", "settings": settings}
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return {"error": str(e)}

@app.get("/api/admin/settings")
async def get_settings():
    """Получить текущие настройки"""
    try:
        config_file = Path("/app/data/settings.json")
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        default_settings = {
            "default_model": "qwen2.5:7b-instruct-q5_K_M",
            "temperature": 0.7,
            "max_tokens": 2000,
            "rag_top_k": 5,
            "enable_web_search": True,
            "enable_rag": True
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=2)
        
        return default_settings
        
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return {"error": str(e)}

# ==================== WEB SEARCH UNIFIED ====================
def web_search_unified(query: str, max_results: int = 5) -> list:
    """
    Unified web search with Google CSE primary and DuckDuckGo fallback.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        
    Returns:
        List of dicts with keys: url, title, snippet
    """
    results = []
    
    # Try Google Custom Search first
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY")
    google_cx = os.getenv("GOOGLE_CSE_CX") or os.getenv("GOOGLE_CSE_ID")
    
    if google_key and google_cx:
        try:
            logger.info(f"🔍 Google CSE search: {query}")
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": google_key,
                "cx": google_cx,
                "q": query,
                "num": max_results
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("items", []):
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", "")
                })
            
            if results:
                logger.info(f"✅ Google CSE: found {len(results)} results")
                return results
                
        except Exception as e:
            logger.warning(f"⚠️ Google CSE failed: {e}, falling back to DuckDuckGo")
    
    # Fallback to DuckDuckGo
    try:
        logger.info(f"🔍 DuckDuckGo search: {query}")
        ddg = DDGS()
        ddg_results = ddg.text(query, max_results=max_results)
        
        for item in ddg_results:
            results.append({
                "url": item.get("href", ""),
                "title": item.get("title", ""),
                "snippet": item.get("body", "")
            })
        
        logger.info(f"✅ DuckDuckGo: found {len(results)} results")
        
    except Exception as e:
        logger.error(f"❌ DuckDuckGo failed: {e}")
    
    return results


# ==================== FASTAPI ИНИЦИАЛИЗАЦИЯ ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ОСНОВНЫЕ ENDPOINTS ====================

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "II-Agent Pro API",
        "version": "5.0",
        "status": "running",
        "features": ["chat", "rag", "web_search", "training", "backup", "admin"]
    }

@app.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    try:
        ollama_response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        ollama_status = "connected" if ollama_response.status_code == 200 else "disconnected"
        
        conn = sqlite3.connect('/app/data/ii_agent.db')
        conn.close()
        db_status = "healthy"
        
        chromadb_status = "available" if CHROMADB_AVAILABLE else "unavailable"
        
        return {
            "status": "healthy",
            "ollama": ollama_status,
            "database": db_status,
            "chromadb": chromadb_status,
            "gpu": "available" if HAS_GPU else "unavailable",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@app.post("/ai-developer/generate")
async def generate_solution(request: dict):
    """енерация решения задачи"""
    try:
        task = request.get('task', '')
        analysis = request.get('analysis', {})
        provider = request.get('provider', 'ollama')
        
        logger.info(f"🔄 Generating solution with {provider}...")
        
        # мпортируем ai_developer
        from ai_developer import AIdeveloper
        ai_dev = AIdev()
        
        # енерируем решение
        solution = await ai_dev.generate_solution(task, analysis, provider)
        
        return {
            'success': True,
            'solution': solution
        }
    except Exception as e:
        logger.error(f"❌ Solution generation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@app.get("/stats")
async def get_stats():
    """Общая статистика системы"""
    try:
        db_stats = get_db_stats()
        
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        c.execute("SELECT model_used, COUNT(*) as count FROM conversations GROUP BY model_used")
        model_usage = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        
        uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
        
        return {
            "total_conversations": db_stats["conversations"],
            "knowledge_items": db_stats["knowledge_items"],
            "model_usage": model_usage,
            "uptime_seconds": int(uptime),
            "chromadb_available": CHROMADB_AVAILABLE,
            "gpu_available": HAS_GPU
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"error": str(e)}

@app.get("/history")
async def get_history(limit: int = 50):
    """История диалогов"""
    try:
        history = get_conversation_history(limit=limit)
        return {
            "history": [{"query": h[0], "response": h[1], "timestamp": h[2]} for h in history],
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"History error: {e}")
        return {"error": str(e)}

# ==================== ЧАТ ENDPOINTS ====================

@app.post("/chat")
async def chat(request: Request):
    """Основной чат endpoint"""
    try:
        data = await request.json()
        query = data.get("query", "")
        use_rag = data.get("use_rag", True)
        use_web = data.get("use_web", False)
        model = data.get("model", "qwen2.5:7b-instruct-q5_K_M")
        provider = data.get("provider", "ollama")
        
        if not query:
            raise HTTPException(status_code=400, detail="Query required")
        
        logger.info(f"Chat query: {query[:100]}...")
        
        context_parts = []
        sources = []
        
        if use_rag and CHROMADB_AVAILABLE:
            try:
                rag_results = search_knowledge_base(query)
                if rag_results:
                    context_parts.append("Информация из базы знаний:")
                    for topic, content, source, confidence in rag_results[:3]:
                        context_parts.append(f"- {content[:200]}")
                        sources.append({"type": "rag", "source": source, "confidence": confidence})
            except Exception as e:
                logger.error(f"RAG search error: {e}")
        
        if use_web:
            try:
                # Определяем тип запроса
                query_type = detect_query_type(query)
                
                # Проверка на запрос погоды
                weather_keywords = ['погода', 'температур', 'градус', 'weather', 'прогноз', 'климат', 'осадки', 'ветер', 'дожд', 'снег']
                if any(keyword in query.lower() for keyword in weather_keywords):
                    # Извлекаем город из запроса (по умолчанию Уфа)
                    city = 'Уфа'
                    for word in ['в ', 'для ', 'на ']:
                        if word in query.lower():
                            parts = query.lower().split(word)
                            if len(parts) > 1:
                                city = parts[1].split()[0].capitalize()
                                break
                    
                    weather_data = get_weather(city)
                    if weather_data:
                        context_parts.append(f"\nТочный прогноз погоды для {weather_data['city']}:")
                        context_parts.append(f"🌡️ Температура: {weather_data['temperature']}°C (ощущается как {weather_data['feels_like']}°C)")
                        context_parts.append(f"☁️ Состояние: {weather_data['description']}")
                        context_parts.append(f"💧 Влажность: {weather_data['humidity']}%")
                        context_parts.append(f"💨 Ветер: {weather_data['wind_speed']} м/с")
                        sources.append({"type": "weather", "city": city, "source": "OpenWeatherMap"})
                
                # Поиск в Google CSE
                web_results = search_web(query, max_results=5)
                
                if web_results:
                    # Обработка в зависимости от типа запроса
                    if query_type == 'news':
                        # ДЛЯ НОВОСТЕЙ: Парсим полные тексты статей
                        context_parts.append("\n📰 Подробная информация из новостных источников:")
                        news_count = 0
                        
                        for result in web_results:
                            if news_count >= 3:  # Максимум 3 новости
                                break
                            
                            # Парсим полный текст статьи
                            article_text = scrape_url(result['url'], max_length=1200)
                            
                            if article_text and len(article_text) > 200:
                                # Успешно спарсили - добавляем полный текст
                                context_parts.append(f"\n🔹 {result['title']}")
                                context_parts.append(f"{article_text}")
                                context_parts.append(f"[Источник: {result['url']}]")
                                sources.append({"type": "web", "title": result['title'], "url": result['url']})
                                news_count += 1
                            else:
                                # Fallback на snippet если парсинг не удался
                                context_parts.append(f"\n- {result['title']}: {result['snippet'][:150]}")
                                sources.append({"type": "web", "title": result['title'], "url": result['url']})
                                news_count += 1
                                
                    elif query_type == 'tutorial':
                        # ДЛЯ ИНСТРУКЦИЙ: Парсим с большой длиной
                        context_parts.append("\n📚 Подробные инструкции:")
                        
                        for result in web_results[:2]:  # Максимум 2 источника
                            article_text = scrape_url(result['url'], max_length=2000)
                            
                            if article_text and len(article_text) > 300:
                                context_parts.append(f"\n📖 {result['title']}")
                                context_parts.append(f"{article_text}")
                                context_parts.append(f"[Источник: {result['url']}]")
                                sources.append({"type": "web", "title": result['title'], "url": result['url']})
                            else:
                                # Fallback на snippet
                                context_parts.append(f"- {result['title']}: {result['snippet']}")
                                sources.append({"type": "web", "title": result['title'], "url": result['url']})
                    
                    else:
                        # ДЛЯ ОБЩИХ ВОПРОСОВ: Используем snippets из Google
                        context_parts.append("\nИнформация из интернета:")
                        for result in web_results[:3]:
                            context_parts.append(f"- {result['title']}: {result['snippet'][:150]} [Ссылка: {result['url']}]")
                            sources.append({"type": "web", "title": result['title'], "url": result['url']})
                            
            except Exception as e:
                logger.error(f"Web search error: {e}")
        
        context = "\n".join(context_parts) if context_parts else ""
        
        full_prompt = f"""Ты - II-Agent Pro, профессиональный AI-ассистент с экспертными знаниями во всех областях.

═══════════════════════════════════════════════════════════════
⚠️ КРИТИЧЕСКИ ВАЖНО - ЯЗЫК ОТВЕТА (ЧИТАЙ ВНИМАТЕЛЬНО!):
═══════════════════════════════════════════════════════════════

🚫 АБСОЛЮТНО ЗАПРЕЩЕНО использовать:
   - Китайский язык: 中文, 汉语, 天气, 预报, 相关, 信息, 等等
   - Английский язык: English, weather, forecast, information, etc.
   - Любые другие языки!

✅ ЕДИНСТВЕННЫЙ РАЗРЕШЁННЫЙ ЯЗЫК: РУССКИЙ (кириллица)!

СТРОГИЕ ПРАВИЛА (НАРУШЕНИЕ = ОШИБКА):
1. Пиши ТОЛЬКО русскими буквами: а, б, в, г, д, е, ё, ж, з, и, й, к, л, м, н, о, п, р, с, т, у, ф, х, ц, ч, ш, щ, ъ, ы, ь, э, ю, я
2. ЗАПРЕЩЕНЫ китайские иероглифы: 中, 文, 天, 气, 预, 报, 相, 关, 信, 息
3. ЗАПРЕЩЕНА латиница в тексте (разрешена только в URL)
4. Если замечаешь что начинаешь писать на другом языке - ОСТАНОВИ СЕБЯ!
5. Перечитывай каждое предложение перед тем как его написать
6. Это правило действует до САМОГО КОНЦА ответа!
7. НЕ ПИШИ китайские комментарии или примечания!

ПРОВЕРКА ПЕРЕД ОТПРАВКОЙ:
- Есть ли в моём ответе китайские иероглифы? → УДАЛИ ИХ!
- Есть ли английские слова в тексте? → ПЕРЕВЕДИ НА РУССКИЙ!
- Весь ответ на русском языке? → ТОЛЬКО ТОГДА ОТПРАВЛЯЙ!

═══════════════════════════════════════════════════════════════
📋 СТРУКТУРА И КАЧЕСТВО ОТВЕТА:
═══════════════════════════════════════════════════════════════

1. ФОРМАТ ОТВЕТА:
   ✓ Начинай с краткого резюме (1-2 предложения)
   ✓ Давай развёрнутый, детальный ответ с конкретными примерами
   ✓ Используй структурированный формат: абзацы, списки, подзаголовки
   ✓ Для сложных тем разбивай на логические разделы

2. КАЧЕСТВО ИНФОРМАЦИИ:
   ✓ Приводи точные данные: цифры, даты, имена, места
   ✓ Используй актуальную информацию из предоставленного контекста
   ✓ Чётко разделяй факты и мнения
   ✓ Если не уверен - так и скажи, не придумывай

3. ПОГОДА И РЕАЛЬНЫЕ ДАННЫЕ:
   ✓ Для погоды используй точные данные из OpenWeatherMap API
   ✓ Указывай: температуру, ощущается как, влажность, ветер, осадки
   ✓ Давай краткий прогноз на основе текущих условий

4. НОВОСТИ И СОБЫТИЯ:
   ✓ Перечисляй события в хронологическом порядке
   ✓ Для каждого события: краткое описание 2-3 предложения
   ✓ Указывай источники, даты, ключевых участников

5. ТЕХНИЧЕСКИЕ ВОПРОСЫ:
   ✓ Давай пошаговые инструкции где применимо
   ✓ Объясняй сложные концепции простым языком
   ✓ Приводи практические примеры

6. СТИЛЬ ОБЩЕНИЯ:
   ✓ Профессиональный, но дружелюбный тон
   ✓ Избегай излишней формальности и "воды"
   ✓ Будь конкретен и по существу
   ✓ Адаптируйся под контекст вопроса

═══════════════════════════════════════════════════════════════
📚 ДОСТУПНАЯ ИНФОРМАЦИЯ:
═══════════════════════════════════════════════════════════════

{context}

═══════════════════════════════════════════════════════════════
❓ ВОПРОС ПОЛЬЗОВАТЕЛЯ:
═══════════════════════════════════════════════════════════════

{query}

═══════════════════════════════════════════════════════════════
💬 ТВОЙ ОТВЕТ (ПОМНИ: ТОЛЬКО РУССКИЙ ЯЗЫК ДО КОНЦА!):
═══════════════════════════════════════════════════════════════
"""
        
        response = query_ai(full_prompt, provider=provider, model=model)
        if response:
            response = filter_chinese_characters(response)
        
        if response is None:
            raise HTTPException(status_code=500, detail="LLM query failed")
        
        conversation_id = save_conversation(query, response, sources, model)
        
        # Автоматически добавляем ссылки к ответу
        if sources:
            links_section = "\n\n---\n📌 **Источники:**\n"
            for src in sources:
                if src.get('type') == 'web':
                    links_section += f"- [{src['title']}]({src['url']})\n"
                elif src.get('type') == 'weather':
                    links_section += f"- Погода: OpenWeatherMap ({src['city']})\n"
            response += links_section
        
        return {
            "response": response,
            "sources": sources,
            "model": model,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== RAG ENDPOINTS ====================

@app.post("/rag/add")
async def add_rag_item(request: Request):
    """Добавить элемент в базу знаний"""
    try:
        data = await request.json()
        topic = data.get("topic", "")
        content = data.get("content", "")
        source = data.get("source", "manual")
        confidence = data.get("confidence", 0.8)
        
        if not topic or not content:
            raise HTTPException(status_code=400, detail="Topic and content required")
        
        add_knowledge(topic, content, source, confidence)
        
        return {"status": "success", "message": "Knowledge added", "topic": topic}
        
    except Exception as e:
        logger.error(f"RAG add error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rag/search")
async def search_rag(query: str, limit: int = 5):
    """Поиск в базе знаний"""
    try:
        results = search_knowledge_base(query)
        
        return {
            "query": query,
            "results": [
                {"topic": r[0], "content": r[1], "source": r[2], "confidence": r[3]}
                for r in results[:limit]
            ],
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return {"error": str(e)}

@app.get("/rag/stats")
async def rag_stats():
    """Статистика RAG"""
    try:
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM knowledge_base")
        total = c.fetchone()[0]
        
        c.execute("SELECT source, COUNT(*) as count FROM knowledge_base GROUP BY source")
        by_source = {row[0]: row[1] for row in c.fetchall()}
        
        c.execute("SELECT AVG(confidence) FROM knowledge_base")
        avg_confidence = c.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            "total_items": total,
            "by_source": by_source,
            "avg_confidence": round(avg_confidence, 2),
            "chromadb_available": CHROMADB_AVAILABLE
        }
        
    except Exception as e:
        logger.error(f"RAG stats error: {e}")
        return {"error": str(e)}

# ==================== TRAINING ENDPOINTS ====================

training_status = {
    "is_running": False,
    "progress": 0,
    "current_source": None,
    "items_processed": 0,
    "start_time": None
}

@app.post("/training/start")
async def start_training(request: Request):
    """Запуск ночного обучения"""
    global training_status
    
    try:
        if training_status["is_running"]:
            return {"status": "error", "message": "Training already running"}
        
        data = await request.json()
        duration_hours = data.get("duration_hours", 4)
        cycles_per_hour = data.get("cycles_per_hour", 4)
        sources = data.get("sources", ["wikipedia", "github", "habr"])
        
        asyncio.create_task(run_training(duration_hours, cycles_per_hour, sources))
        
        return {
            "status": "started",
            "duration_hours": duration_hours,
            "cycles_per_hour": cycles_per_hour,
            "sources": sources
        }
        
    except Exception as e:
        logger.error(f"Training start error: {e}")
        return {"error": str(e)}

async def run_training(duration_hours, cycles_per_hour, sources):
    """Фоновое обучение"""
    global training_status
    
    training_status["is_running"] = True
    training_status["progress"] = 0
    training_status["start_time"] = datetime.now().isoformat()
    
    try:
        total_cycles = duration_hours * cycles_per_hour
        
        for cycle in range(total_cycles):
            source = sources[cycle % len(sources)]
            training_status["current_source"] = source
            training_status["progress"] = int((cycle / total_cycles) * 100)
            
            if source == "wikipedia":
                await train_from_wikipedia()
            elif source == "github":
                await train_from_github()
            elif source == "habr":
                await train_from_habr()
            
            training_status["items_processed"] += 1
            
            await asyncio.sleep(60 * 60 / cycles_per_hour)
        
        training_status["progress"] = 100
        logger.info(f"Training completed: {training_status['items_processed']} items")
        
    except Exception as e:
        logger.error(f"Training error: {e}")
    finally:
        training_status["is_running"] = False

async def train_from_wikipedia():
    """Обучение на Wikipedia"""
    try:
        topics = ["Python", "Artificial Intelligence", "Machine Learning", "Neural Network"]
        topic = topics[training_status["items_processed"] % len(topics)]
        
        page = wikipedia.page(topic, auto_suggest=True)
        content = page.content[:1000]
        
        add_knowledge(topic, content, f"wikipedia:{page.url}", confidence=0.9)
        logger.info(f"Added Wikipedia article: {topic}")
        
    except Exception as e:
        logger.error(f"Wikipedia training error: {e}")

async def train_from_github():
    """Обучение на GitHub (заглушка)"""
    logger.info("GitHub training (placeholder)")
    pass

async def train_from_habr():
    """Обучение на Habr (заглушка)"""
    logger.info("Habr training (placeholder)")
    pass

@app.get("/training/status")
async def get_training_status():
    """Статус обучения"""
    return training_status

@app.post("/training/stop")
async def stop_training():
    """Остановка обучения"""
    global training_status
    training_status["is_running"] = False
    return {"status": "stopped"}

# ==================== BACKUP ENDPOINTS ====================

@app.post("/backup/create")
async def create_backup_endpoint(request: Request):
    """Создание бэкапа"""
    try:
        data = await request.json()
        description = data.get("description", "Manual backup")
        
        result = backup_system.create_backup(description)
        
        return {
            "status": "success",
            "backup_id": result.get("commit_hash", "unknown"),
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Backup creation error: {e}")
        return {"error": str(e)}

@app.get("/backup/list")
async def list_backups():
    """Список бэкапов"""
    try:
        backups = backup_system.list_backups()
        return {"backups": backups, "count": len(backups)}
    except Exception as e:
        logger.error(f"Backup list error: {e}")
        return {"error": str(e)}

@app.post("/backup/restore")
async def restore_backup(request: Request):
    """Восстановление бэкапа"""
    try:
        data = await request.json()
        backup_id = data.get("backup_id")
        
        if not backup_id:
            raise HTTPException(status_code=400, detail="backup_id required")
        
        result = backup_system.restore_backup(backup_id)
        
        return {"status": "success", "backup_id": backup_id, "message": "Backup restored"}
        
    except Exception as e:
        logger.error(f"Backup restore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== TEST ENDPOINTS ====================

@app.get("/test/run")
async def run_tests():
    """Запуск тестов"""
    try:
        results = test_system.run_all_tests()
        return {
            "test_results": results,
            "total_tests": len(results),
            "passed": sum(1 for r in results if r.get("status") == "passed"),
            "failed": sum(1 for r in results if r.get("status") == "failed")
        }
    except Exception as e:
        logger.error(f"Test error: {e}")
        return {"error": str(e)}

# ==================== WEBSOCKET ====================

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket для чата"""
    await websocket.accept()
    logger.info("WebSocket chat connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            query = message.get("query", "")
            model = message.get("model", "qwen2.5:7b-instruct-q5_K_M")
            
            if not query:
                await websocket.send_json({"error": "Query required"})
                continue
            
            full_response = ""
            async for chunk in stream_ollama(query, model=model):
                full_response += chunk
                await websocket.send_json({"type": "chunk", "content": chunk})
            
            await websocket.send_json({"type": "done", "full_response": full_response})
            
            save_conversation(query, full_response, [], model)
            
    except WebSocketDisconnect:
        logger.info("WebSocket chat disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass

@app.websocket("/ws/self-healing")
async def websocket_self_healing(websocket: WebSocket):
    """WebSocket для мониторинга self-healing"""
    await websocket.accept()
    logger.info("WebSocket self-healing connected")
    
    try:
        while True:
            status = {
                "timestamp": datetime.now().isoformat(),
                "status": "healthy",
                "last_check": "OK",
                "auto_fixes": 0,
                "system_load": psutil.cpu_percent()
            }
            await websocket.send_json(status)
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        logger.info("WebSocket self-healing disconnected")
    except Exception as e:
        logger.error(f"WebSocket self-healing error: {e}")

# ==================== WEB SEARCH ENDPOINTS ====================

@app.get("/search/web")
# ==================== WEB SEARCH PRIORITY ====================
# 1. Google Custom Search (primary - has API key)
# 2. Fallback to DuckDuckGo if Google fails
# ==============================================================

async def web_search_endpoint(query: str, max_results: int = 5):
    """Поиск в интернете"""
    try:
        results = search_web(query, max_results=max_results)
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Web search endpoint error: {e}")
        return {"error": str(e)}

@app.post("/search/scrape")
async def scrape_endpoint(request: Request):
    """Извлечение текста с URL"""
    try:
        data = await request.json()
        url = data.get("url")
        
        if not url:
            raise HTTPException(status_code=400, detail="URL required")
        
        text = scrape_url(url)
        
        return {"url": url, "text": text, "length": len(text)}
        
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== АЛИАСЫ ДЛЯ СОВМЕСТИМОСТИ (ИСПРАВЛЕНИЕ 404) ====================

@app.post("/ask")
async def ask_alias(request: Request):
    """Алиас для /chat"""
    return await chat(request)

@app.get("/api/status")
async def status_alias():
    """Алиас для /stats"""
    return await get_stats()

@app.get("/api/rag/stats")
async def rag_stats_alias():
    """Алиас для /rag/stats"""
    return await rag_stats()

@app.get("/api/training/status")
async def training_status_alias():
    """Алиас для /training/status"""
    return await get_training_status()

@app.post("/api/training/start")
async def training_start_alias(request: Request):
    """Алиас для /training/start"""
    return await start_training(request)

@app.get("/api/model/stats")
async def model_stats_alias():
    """Статистика моделей"""
    try:
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        c.execute("SELECT model_used, COUNT(*) as count FROM conversations GROUP BY model_used")
        stats = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        
        return {"model_usage": stats, "total": sum(stats.values())}
    except Exception as e:
        logger.error(f"Model stats error: {e}")
        return {"error": str(e)}

@app.get("/api/expert/requests")
async def expert_requests_alias():
    """История запросов к экспертным моделям"""
    try:
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        c.execute("""
            SELECT id, query, model_used, timestamp, rating 
            FROM conversations 
            WHERE model_used LIKE '%expert%' OR model_used LIKE '%32b%'
            ORDER BY timestamp DESC 
            LIMIT 50
        """)
        
        results = []
        for row in c.fetchall():
            results.append({
                "id": row[0],
                "query": row[1],
                "model": row[2],
                "timestamp": row[3],
                "rating": row[4],
                "status": "completed"
            })
        
        conn.close()
        return {"requests": results, "total": len(results)}
    except Exception as e:
        logger.error(f"Expert requests error: {e}")
        return {"error": str(e)}

# ==================== ДОПОЛНИТЕЛЬНЫЕ ENDPOINTS ====================

@app.post("/models/switch")
async def switch_model(request: Request):
    """Переключение модели по умолчанию"""
    try:
        data = await request.json()
        model = data.get("model")
        
        if not model:
            raise HTTPException(status_code=400, detail="Model name required")
        
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        models = response.json().get("models", [])
        model_names = [m["name"] for m in models]
        
        if model not in model_names:
            raise HTTPException(status_code=404, detail=f"Model {model} not found")
        
        settings = await get_settings()
        settings["default_model"] = model
        
        config_file = Path("/app/data/settings.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        
        return {"status": "success", "model": model, "message": f"Default model switched to {model}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model switch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conversation/rate")
async def rate_conversation(request: Request):
    """Оценка качества ответа"""
    try:
        data = await request.json()
        conversation_id = data.get("conversation_id")
        rating = data.get("rating")
        
        if not conversation_id or rating is None:
            raise HTTPException(status_code=400, detail="conversation_id and rating required")
        
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        c.execute("UPDATE conversations SET rating = ? WHERE id = ?", (rating, conversation_id))
        conn.commit()
        conn.close()
        
        return {"status": "success", "conversation_id": conversation_id, "rating": rating}
        
    except Exception as e:
        logger.error(f"Rating error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge/bulk-add")
async def bulk_add_knowledge(request: Request):
    """Массовое добавление знаний"""
    try:
        data = await request.json()
        items = data.get("items", [])
        
        if not items:
            raise HTTPException(status_code=400, detail="Items required")
        
        conn = sqlite3.connect('/app/data/ii_agent.db')
        c = conn.cursor()
        
        for item in items:
            topic = item.get("topic")
            content = item.get("content")
            source = item.get("source", "bulk_import")
            confidence = item.get("confidence", 0.7)
            
            if topic and content:
                c.execute(
                    "INSERT INTO knowledge_base (topic, content, source, confidence) VALUES (?, ?, ?, ?)",
                    (topic, content, source, confidence)
                )
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "items_added": len(items)}
        
    except Exception as e:
        logger.error(f"Bulk add error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/disk-usage")
async def get_disk_usage():
    """Использование диска по папкам"""
    try:
        data_dir = Path("/app/data")
        
        usage = {}
        for item in data_dir.iterdir():
            if item.is_dir():
                size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                usage[item.name] = {
                    "size_bytes": size,
                    "size_mb": round(size / (1024**2), 2),
                    "size_gb": round(size / (1024**3), 2)
                }
            elif item.is_file():
                size = item.stat().st_size
                usage[item.name] = {
                    "size_bytes": size,
                    "size_mb": round(size / (1024**2), 2)
                }
        
        return {
            "usage": usage,
            "total_mb": round(sum(u["size_bytes"] for u in usage.values()) / (1024**2), 2)
        }
        
    except Exception as e:
        logger.error(f"Disk usage error: {e}")
        return {"error": str(e)}

# ==================== STARTUP & SHUTDOWN ====================


# ==================== ENDPOINT ДЛЯ ЗАГРУЗКИ МОДЕЛЕЙ (EN) ====================

@app.get("/models")
async def get_models_en():
    """Получить список доступных моделей Ollama"""
    try:
        response = requests.get("http://host.docker.internal:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models_list = []
            
            for model in data.get("models", []):
                models_list.append({
                    "name": model.get("name", ""),
                    "size": model.get("size", 0),
                    "modified": model.get("modified_at", "")
                })
            
            return {"models": models_list, "count": len(models_list)}
        else:
            logger.warning(f"Ollama returned status {response.status_code}")
            return {"models": [], "count": 0}
            
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return {"models": [], "count": 0, "error": str(e)}

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("=" * 50)
    logger.info("🚀 II-Agent Pro v5.0 Starting...")
    logger.info("=" * 50)
    
    app.state.start_time = time.time()
    
    # Проверка Ollama
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            logger.info(f"✅ Ollama connected: {len(models)} models available")
        else:
            logger.warning("⚠️ Ollama not responding")
    except Exception as e:
        logger.error(f"❌ Ollama connection failed: {e}")
    
    # Проверка БД
    try:
        conn = sqlite3.connect('/app/data/ii_agent.db')
        conn.close()
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
    
    # Проверка ChromaDB
    if CHROMADB_AVAILABLE:
        logger.info("✅ ChromaDB available")
    else:
        logger.warning("⚠️ ChromaDB not available")
    
    # Проверка GPU
    if HAS_GPU:
        logger.info("✅ GPU detected")
    else:
        logger.warning("⚠️ No GPU detected")
    
    # Инициализация систем
    try:
        backup_system
        logger.info("✅ Backup system initialized")
    except Exception as e:
        logger.error(f"❌ Backup system error: {e}")
    
    try:
        test_system
        logger.info("✅ Test system initialized")
    except Exception as e:
        logger.error(f"❌ Test system error: {e}")
    
    # Загрузка AGENT_INSTRUCTIONS.md
    try:
        instructions_path = Path("/app/AGENT_INSTRUCTIONS.md")
        if instructions_path.exists():
            with open(instructions_path, 'r', encoding='utf-8') as f:
                instructions = f.read()
            add_knowledge(
                "Agent Instructions",
                instructions,
                "agent_instructions",
                confidence=1.0
            )
            logger.info("✅ Agent instructions loaded")
        else:
            logger.warning("⚠️ AGENT_INSTRUCTIONS.md not found")
    except Exception as e:
        logger.error(f"❌ Agent instructions error: {e}")
    
    logger.info("=" * 50)
    logger.info("✅ II-Agent Pro ready!")
    logger.info("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    """Завершение работы"""
    logger.info("🛑 II-Agent Pro shutting down...")
    
    if training_status["is_running"]:
        training_status["is_running"] = False
        logger.info("⏹️ Training stopped")
    
    try:
        backup_system.create_backup("Automatic shutdown backup")
        logger.info("💾 Final backup created")
    except Exception as e:
        logger.error(f"❌ Final backup error: {e}")
    
    logger.info("👋 Goodbye!")

# ==================== ЗАПУСК СЕРВЕРА ====================



# ============ Ы ТЫ ============

@app.post("/api/rag/upload")
async def upload_file(file: UploadFile):
    """агрузка файла в RAG"""
    try:
        content = await file.read()
        text = content.decode('utf-8')
        rag.add_document(text, source=f"upload:{file.filename}")
        return {"success": True, "message": f"айл {file.filename} загружен"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/rag/search")
async def search_rag(query: str, limit: int = 5):
    """оиск в RAG"""
    try:
        results = rag.search(query, limit=limit)
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/rag/train")
async def train_from_url(url: str):
    """бучение с URL"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()
        
        rag.add_document(text, source=f"url:{url}")
        return {"success": True, "message": f"бучено с {url}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/models")
async def list_models():
    """Список доступных моделей"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags")
        return response.json()
    except:
        return {"models": []}



# ==================== AI DEVELOPER API ====================
from ai_developer import AIDeveloper

ai_dev = AIDeveloper()

@app.post("/ai-dev/analyze")
async def ai_dev_analyze(request: Request):
    """нализ задачи AI-разработчиком"""
    try:
        data = await request.json()
        task = data.get('task', '')
        
        if not task:
            return JSONResponse({'error': 'Task is required'}, status_code=400)
        
        provider = data.get("provider", "groq")
        analysis = ai_dev.analyze_task(task, provider)
        return JSONResponse({'success': True, 'analysis': analysis})
    except Exception as e:
        logger.error(f'AI Dev analyze error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/backup")
async def ai_dev_backup(request: Request):
    """Создание бэкапа файлов"""
    try:
        data = await request.json()
        files = data.get('files', [])
        task = data.get('task', 'Manual backup')
        
        backup_id = ai_dev.create_backup(files, task)
        return JSONResponse({'success': True, 'backup_id': backup_id})
    except Exception as e:
        logger.error(f'AI Dev backup error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/generate")
async def ai_dev_generate(request: Request):
    """енерация решения"""
    try:
        data = await request.json()
        task = data.get('task', '')
        file_path = data.get('file_path', '')
        current_code = data.get('current_code', '')
        
        solution = ai_dev.generate_solution(task, file_path, current_code)
        return JSONResponse({'success': True, 'solution': solution})
    except Exception as e:
        logger.error(f'AI Dev generate error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/apply")
async def ai_dev_apply(request: Request):
    """рименить изменения"""
    try:
        data = await request.json()
        file_path = data.get('file_path', '')
        new_code = data.get('new_code', '')
        
        success = ai_dev.apply_changes(file_path, new_code)
        return JSONResponse({'success': success})
    except Exception as e:
        logger.error(f'AI Dev apply error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.post("/ai-dev/rollback")
async def ai_dev_rollback(request: Request):
    """ткат изменений"""
    try:
        data = await request.json()
        backup_id = data.get('backup_id', '')
        
        success = ai_dev.rollback(backup_id)
        return JSONResponse({'success': success})
    except Exception as e:
        logger.error(f'AI Dev rollback error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.get("/ai-dev/backups")
async def ai_dev_list_backups():
    """Список бэкапов"""
    try:
        backups = ai_dev.list_backups()
        return JSONResponse({'success': True, 'backups': backups})
    except Exception as e:
        logger.error(f'AI Dev list backups error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)

@app.get("/ai-dev/diff/{backup_id}")
async def ai_dev_get_diff(backup_id: str, file_path: str):
    """олучить diff"""
    try:
        diff = ai_dev.get_diff(file_path, backup_id)
        return JSONResponse({'success': True, 'diff': diff})
    except Exception as e:
        logger.error(f'AI Dev diff error: {e}')
        return JSONResponse({'error': str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    
    Path("/app/data").mkdir(parents=True, exist_ok=True)
    Path("/app/logs").mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
        workers=1
    )

    global gigachat_client
    gigachat_client = GigaChatAPI()
    gigachat_client.connect()
