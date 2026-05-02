FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rain_bot.py .

EXPOSE 8000

CMD ["python", "rain_bot.py"]
