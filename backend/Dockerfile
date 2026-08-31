FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY samples ./samples

EXPOSE 43124

HEALTHCHECK --interval=10s --timeout=5s --retries=8 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:43124/api/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "43124"]
