.PHONY: dev backend frontend build install

ROOT := $(abspath ../..)
FRONTEND := frontend

dev: backend

backend:
	cd $(ROOT) && uv run --with uvicorn python tools/onboarding_mapper/run.py --reload --port 8765

frontend:
	cd $(FRONTEND) && npm install && npm run dev

build:
	cd $(FRONTEND) && npm install && npm run build

install:
	cd $(FRONTEND) && npm install
