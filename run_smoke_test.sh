#!/usr/bin/env bash
# End-to-end check on SYNTHETIC data (~1 min). Starts the API, streams transactions, detects rings.
set -e
cd "$(dirname "$0")/src"
rm -f ../artifacts/cases.db
python generate_data.py
python train_model.py
uvicorn api:app --port 8100 --log-level warning & API=$!
trap "kill $API" EXIT
sleep 8
python stream_sim.py --n 5000
python graph_rings.py
cd .. && python -m pytest -q tests
