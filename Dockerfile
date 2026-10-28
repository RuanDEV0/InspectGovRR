FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic não consulta o banco, mas o Django precisa das variáveis para iniciar.
RUN DJANGO_SECRET_KEY=build-only-not-used-at-runtime \
    DB_NAME=build DB_USER=build DB_PASSWORD=build DB_HOST=localhost DB_PORT=5432 \
    python manage.py collectstatic --noinput \
    && addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app
EXPOSE 8000

CMD ["sh", "/app/bin/start-web.sh"]
