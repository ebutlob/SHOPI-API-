#!/bin/bash

echo "🚀 Deploying SHOPI API..."
pip install -r requirements.txt
uvicorn api.index:app --host 0.0.0.0 --port 8081 --workers 4
