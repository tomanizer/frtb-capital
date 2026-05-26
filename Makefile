PYTHON ?= python3
VENV ?= .venv
PYTHON_BIN := $(VENV)/bin/python
PIP := $(PYTHON_BIN) -m pip

.PHONY: venv install test lint typecheck check demo clean

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON_BIN) -m pytest

lint:
	$(PYTHON_BIN) -m ruff check src tests

typecheck:
	$(PYTHON_BIN) -m mypy src

check: lint typecheck test

demo:
	$(PYTHON_BIN) examples/run_demo.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist *.egg-info
