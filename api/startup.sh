#!/usr/bin/env bash
gunicorn -k uvicorn.workers.UvicornWorker api.main:app --bind=0.0.0.0:${PORT:-8000} --timeout 120
