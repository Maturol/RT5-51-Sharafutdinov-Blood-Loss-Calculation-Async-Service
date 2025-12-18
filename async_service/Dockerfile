FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# Создаем директорию для статики
RUN mkdir -p /app/static

# Запускаем Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]