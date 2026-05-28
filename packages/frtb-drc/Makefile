PYTHON ?= python3
VENV ?= .venv
PYTHON_BIN ?= $(VENV)/bin/python
PIP := $(PYTHON_BIN) -m pip

.PHONY: venv install test lint format format-check typecheck check examples demo clean

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON_BIN) -m pytest

lint:
	$(PYTHON_BIN) -m ruff check src tests examples scripts

format:
	$(PYTHON_BIN) -m ruff format src tests examples scripts

format-check:
	$(PYTHON_BIN) -m ruff format --check src tests examples scripts

typecheck:
	$(PYTHON_BIN) -m mypy src

check: lint format-check typecheck test

examples:
	$(PYTHON_BIN) examples/run_demo.py

demo: examples

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist *.egg-info
