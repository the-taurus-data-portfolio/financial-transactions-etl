.PHONY: setup install test clean run logs-clean

VENV_NAME := venv
PYTHON := python3

setup:
	@echo "Setting up virtual environment..."
	$(PYTHON) -m venv $(VENV_NAME)
	@echo "Installing/Upgrading pip..."
	./$(VENV_NAME)/bin/pip install --upgrade pip
	@echo "Installing dependencies from requirements.txt..."
	./$(VENV_NAME)/bin/pip install -r requirements.txt
	@echo "Setup complete!"

install:
	@echo "Installing dependencies into the active virtual environment (assuming one is active)..."
	./$(VENV_NAME)/bin/pip install -r requirements.txt

run:
	@echo "Usage: make run INPUT_DIR=path/to/csv/files"
	@if [ -z "$(INPUT_DIR)" ]; then \
       echo "Please specify INPUT_DIR. Example: make run INPUT_DIR=./data"; \
    else \
       ./$(VENV_NAME)/bin/python src/main.py --input-dir $(INPUT_DIR); \
    fi

test:
	@echo "Running tests..."
	./$(VENV_NAME)/bin/python -m pytest tests/ -v

clean:
	@echo "Cleaning up build artifacts and virtual environment..."
	rm -rf $(VENV_NAME)
	rm -rf __pycache__
	rm -rf src/__pycache__
	rm -rf src/*/__pycache__
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo "Clean complete!"

logs-clean:
	@echo "Cleaning up logs and output directories..."
	rm -rf logs/*
	rm -rf output/*
	@echo "Logs and output cleaned!"