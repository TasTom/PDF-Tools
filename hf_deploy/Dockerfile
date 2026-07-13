FROM python:3.11-slim

RUN useradd -m -u 1000 user

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

RUN mkdir -p /app/data/uploads /app/data/outputs && \
    chown -R user:user /app/data

USER user

EXPOSE 8000
ENV PORT=8000

CMD exec uvicorn app.main:app --host 0.0.0.0 --port 8000
