# Используем официальный образ Python
FROM python:3.10-slim

# Установка рабочей директории
WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# Создаем пустую базу данных (или она создастся при первом запуске)
# Выставляем порт
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]