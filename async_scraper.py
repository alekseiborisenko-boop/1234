import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class AsyncScraper:
    def __init__(self, timeout: int = 10, max_concurrent: int = 5):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_concurrent = max_concurrent
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru,en;q=0.9',
        }
    
    async def fetch_url(self, session: aiohttp.ClientSession, url: str, max_length: int = 2000) -> Dict[str, any]:
        '''агрузить один URL'''
        try:
            async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                if response.status != 200:
                    logger.warning(f'⚠️ {url}: HTTP {response.status}')
                    return {'url': url, 'text': '', 'error': f'HTTP {response.status}'}
                
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                
                # далить скрипты и стили
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                
                # звлечь текст
                text = soup.get_text(separator=' ', strip=True)
                text = ' '.join(text.split())  # чистка пробелов
                
                # брезать до max_length
                if len(text) > max_length:
                    text = text[:max_length] + '...'
                
                logger.info(f'✅ {url}: {len(text)} chars')
                return {'url': url, 'text': text, 'error': None}
                
        except asyncio.TimeoutError:
            logger.warning(f'⏱️ Timeout: {url}')
            return {'url': url, 'text': '', 'error': 'Timeout'}
        except Exception as e:
            logger.error(f'❌ Error scraping {url}: {e}')
            return {'url': url, 'text': '', 'error': str(e)}
    
    async def fetch_multiple(self, urls: List[str], max_length: int = 2000, priority_urls: int = 2) -> List[Dict[str, any]]:
        '''
        агрузить несколько URL параллельно
        priority_urls: первые N URL получают полный текст, остальные только snippet
        '''
        if not urls:
            return []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, url in enumerate(urls[:self.max_concurrent]):
                # ервые priority_urls получают больше текста
                length = max_length if i < priority_urls else max_length // 2
                tasks.append(self.fetch_url(session, url, length))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # ильтр успешных результатов
            valid_results = []
            for result in results:
                if isinstance(result, dict) and result.get('text'):
                    valid_results.append(result)
            
            logger.info(f'📊 Scraped {len(valid_results)}/{len(urls)} URLs successfully')
            return valid_results
    
    def scrape_sync(self, urls: List[str], max_length: int = 2000, priority_urls: int = 2) -> List[Dict[str, any]]:
        '''Синхронная обёртка для вызова из обычного кода'''
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.fetch_multiple(urls, max_length, priority_urls))
