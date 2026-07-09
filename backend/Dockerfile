FROM python:3.12-slim

# psycopg2-binary needs libpq at runtime; build-essential/libpq-dev only
# matter if you ever switch to the non-binary psycopg2 package.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as a non-root user inside the container.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
