FROM python:3.11-slim

WORKDIR /app

# ✅ Установка системных зависимостей (ДОБАВЛЕН GIT!)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Копирование ВСЕХ файлов (проще и безопаснее)
COPY . .

# Создание папок для данных
RUN mkdir -p /app/data /app/logs /app/backups

# ✅ Создание non-root пользователя
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Запуск
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
