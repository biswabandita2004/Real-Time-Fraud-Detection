
# AIML-01 – Real-Time Financial Fraud Detection Platform

A machine learning-based fraud detection platform that analyzes financial transactions, predicts fraud risk, and classifies transactions into approve, review, or block decisions.

## 1. Project Overview

This project demonstrates a real-time fraud detection workflow using LightGBM, FastAPI, Redis, Redpanda Kafka, and Streamlit.

The system includes:
- Synthetic transaction data generation.
- Feature engineering and fraud classification.
- HTTP-based transaction scoring.
- Kafka-based transaction streaming.
- Redis feature and scoring state.
- Fraud ring detection.
- Analyst dashboard and monitoring metrics.

## 2. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Machine Learning | LightGBM, Scikit-learn |
| Data Processing | Pandas, NumPy |
| API | FastAPI |
| Streaming | Redpanda Kafka |
| Feature State | Redis |
| Database | SQLite |
| Dashboard | Streamlit |
| Monitoring | Prometheus Metrics |
| Deployment | Docker Compose |
| Testing | Pytest |

## 3. Architecture

The project has two workflows:

1. Prototype HTTP scoring: transaction simulator sends transactions to FastAPI for model scoring.
2. Production demo streaming: Redpanda receives transactions, Kafka Worker processes them, and scored results are published to the scored topic.

See `docs/ARCHITECTURE.md` for the architecture diagrams.

## 4. Dataset

The experiments use a synthetic dataset containing 120,975 transactions.

- Fraud rate: approximately 0.81%.
- Fraud patterns are artificially generated.
- Data is split into 60% training, 20% validation, and 20% testing.

These results are experimental and do not represent real-world banking performance.

## 5. Model Evaluation

| Metric | Result |
|---|---:|
| ROC-AUC | 0.999929 |
| PR-AUC | 0.993729 |
| Precision at review threshold | 0.7807 |
| Recall at review threshold | 0.9932 |

The system uses two decision thresholds:
- Review threshold: 0.02
- Block threshold: 0.90

Thresholds are based on assumed business costs.

## 6. Performance Testing

HTTP replay results:

- Transactions processed: 5,147
- Flagged transactions: 141
- Approved transactions: 5,006
- Server latency p50: 4.39 ms
- Server latency p95: 6.65 ms
- Server latency p99: 9.29 ms
- HTTP latency p50: 12.26 ms
- HTTP latency p95: 16.92 ms

These are results from the local demo environment.

## 7. Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 8. Run with Docker Compose

Configure the required environment variables in `.env`.

Start the services:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Check service status:

```bash
docker compose -f docker-compose.prod.yml --env-file .env ps
```

## 9. Access the Application

- API health: http://localhost:8100/healthz
- API readiness: http://localhost:8100/readyz
- Prometheus metrics: http://localhost:8100/metrics
- Streamlit dashboard: http://localhost:8501

The scoring endpoint is `POST /v1/score` and requires an `X-API-Key` header.

## 10. Testing

Run automated tests:

```bash
python -m pytest -q
```

Latest test result: 18 passed.

Kafka streaming was verified by publishing a transaction to the `transactions` topic and confirming its scored result in the `scored` topic.

Redis connectivity and stored scoring state were also verified.

## 11. Project Limitations

- Only synthetic transaction data was used.
- Real banking data has not been evaluated.
- Model performance may differ on real-world transactions.
- Production deployment requires security review, real-world validation, load testing, and managed infrastructure.

## 12. Future Improvements

- Evaluate the model using real, approved transaction datasets.
- Improve fraud detection with additional behavioral features.
- Add model drift monitoring.
- Strengthen authentication and access control.
- Perform large-scale load and reliability testing.

## Author

Biswabandita Mahunta
