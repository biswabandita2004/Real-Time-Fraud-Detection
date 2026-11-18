# Individual Reflection – Biswabandita Mahunta (AIML-01)

### What I owned
I worked on the AIML-01 fraud detection project, including understanding the project structure, running the data generation and model training workflows, testing the FastAPI scoring API, and validating the Docker Compose deployment. I also tested Redis connectivity, Kafka message processing, and the Streamlit dashboard. I debugged environment and Kafka connectivity issues during testing.

### What I learned
- Handling imbalanced datasets and evaluating models using ROC-AUC and PR-AUC.
- Feature engineering for transaction fraud detection.
- Building and testing REST APIs using FastAPI.
- Understanding Kafka producers, consumers, and streaming workflows.
- Using Redis for feature and scoring state.
- Running multi-service applications using Docker Compose.
- Understanding fraud-ring detection using graph relationships.

### What was hard / what I would do differently
Debugging Docker networking and Kafka DNS connectivity was challenging. I learned to verify service health, network connectivity, logs, and message delivery systematically. In future, I would plan testing earlier and evaluate the model with real, approved transaction data.

### Tools I used for the first time
- Redpanda Kafka
- Redis
- Docker Compose
- FastAPI
- Streamlit
- Pytest
- PowerShell
- Git and GitHub
