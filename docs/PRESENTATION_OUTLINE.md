
# AIML-01 – 10-Minute Project Presentation

## Slide 1: Problem Statement
- Financial fraud causes financial losses.
- Traditional rule-based systems may miss complex fraud patterns.
- Objective: Build a machine learning-based fraud detection platform.

## Slide 2: Dataset
- Generated 120,975 synthetic transactions.
- Fraud rate: approximately 0.81%.
- Fraud patterns were artificially generated.
- Dataset split: 60% training, 20% validation, 20% testing.

## Slide 3: Technology and Architecture
- Python and LightGBM for machine learning.
- FastAPI for HTTP scoring.
- Redpanda Kafka for transaction streaming.
- Redis for feature state.
- SQLite for demo case storage.
- Streamlit for analyst dashboard.
- Docker Compose for deployment.

## Slide 4: Feature Engineering
- Transaction amount and log amount.
- Transaction frequency.
- Device and account relationships.
- Time-based transaction features.
- Country mismatch and new-device indicators.
- Point-in-time feature engineering to reduce data leakage.

## Slide 5: Model Evaluation
- ROC-AUC: 0.999929
- PR-AUC: 0.993729
- Precision at review threshold: 0.7807
- Recall at review threshold: 0.9932
- Review threshold: 0.02
- Block threshold: 0.90

Note: These are results on synthetic test data.

## Slide 6: Performance Testing
HTTP replay:
- Transactions processed: 5,147
- Flagged: 141
- Approved: 5,006
- Server latency p50: 4.39 ms
- Server latency p95: 6.65 ms
- Server latency p99: 9.29 ms

## Slide 7: Fraud Ring Detection and Dashboard
- Identify linked accounts through shared devices.
- Display flagged transactions.
- Monitor model performance and scoring latency.
- Provide an analyst dashboard using Streamlit.

## Slide 8: Deployment, Challenges and Future Work
- Docker Compose deployment verified.
- Kafka transaction processing verified end-to-end.
- Redis state storage verified.
- Automated tests: 18 passed.
- A temporary Kafka DNS issue was resolved during testing.
- Future work: real-world data validation, model drift monitoring, security review and large-scale load testing.

## Conclusion
This project demonstrates an end-to-end fraud detection workflow using machine learning, streaming infrastructure, APIs and an analyst dashboard.

The results are experimental and do not establish real-world banking performance.
