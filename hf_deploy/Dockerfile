FROM python:3.11-slim

RUN useradd -m -u 1000 user

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

USER user

EXPOSE 8000
ENV PORT=8000

CMD exec uvicorn app.main:app --host 0.0.0.0 --port 8000
