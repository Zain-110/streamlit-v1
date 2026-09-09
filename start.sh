#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
python -m pip install -r requirements.txt
exec streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
