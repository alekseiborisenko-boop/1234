# -*- coding: utf-8 -*-
"""
II-Agent Code Assistant
Помощник для ненерации, анализа и выполнения кода
"""
import os
import re
import ast
import json
import logging
import sys
import subprocess
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ======================== тОНФИГУРАЦИЯ =========================

CODE_SANDBOX_DIR = Path("/app/sandbox")
CODE_SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

# Разрешённый импорты (whitelist)
ALLOWED_IMPORTS = {
    'math', 'random', 'datetime', 'time', 'json', 're',
    'collections', 'itertools', 'functools', 'operator',
    'statistics', 'decimal', 'fractions'
}

# ======================== ВЫЗОВ LLM =========================

def call_llm(prompt: str, model: str = "qwen2.5:7b") -> str:
    """Вызов LLM для генерации кода"""
    try:
        import requests
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json().get('response', '')
        else:
            logger.error(f"LLM call failed: {response.status_code}")
            return ""
            
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return ""
