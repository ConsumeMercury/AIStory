FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV AISTORY_HOST=0.0.0.0
ENV AISTORY_PORT=8765

EXPOSE 8765

CMD ["python", "api/server.py"]
