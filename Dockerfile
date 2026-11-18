FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*   # LightGBM needs OpenMP
WORKDIR /app
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt
COPY src ./src
COPY app ./app
RUN useradd -m appuser && mkdir /data && chown appuser /data
USER appuser
ENV PYTHONUNBUFFERED=1 CASES_DB=/data/cases.db
WORKDIR /app/src
CMD ["uvicorn", "api_prod:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100", "--workers", "2"]
