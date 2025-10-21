content = open(r'E:\ii-agent\backend\main.py', 'r', encoding='utf-8').read()

# айти и заменить первый блок
marker1 = """        }

        logger.info(f'🔍 Google CSE search: {query}')
        response = requests.get(url, params=params, timeout=10)"""

replacement1 = """        }

        # Check cache first
        cache_key = f"{query}_{max_results}"
        cached_results = cache_manager.get(cache_key, 'google_cse')
        if cached_results:
            logger.info(f'🎯 Cache HIT for Google CSE: {query[:50]}...')
            return cached_results

        logger.info(f'🔍 Google CSE search: {query}')
        response = requests.get(url, params=params, timeout=10)"""

if marker1 in content:
    content = content.replace(marker1, replacement1, 1)
    print('✅ Cache CHECK added')
else:
    print('⚠️ Marker 1 not found')

# торой блок - save
marker2 = """            logger.info(f'✅ Found {len(results)} results from Google CSE')
            return results"""

replacement2 = """            # Save to cache
            if results:
                cache_manager.set(cache_key, results, 'google_cse', ttl=3600)
                logger.info(f'💾 Cached {len(results)} results')
            
            logger.info(f'✅ Found {len(results)} results from Google CSE')
            return results"""

if marker2 in content:
    content = content.replace(marker2, replacement2, 1)
    print('✅ Cache SAVE added')
else:
    print('⚠️ Marker 2 not found')

open(r'E:\ii-agent\backend\main.py', 'w', encoding='utf-8').write(content)
print('\n🎉 Cache fully integrated!')
