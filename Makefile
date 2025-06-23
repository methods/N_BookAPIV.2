.DEFAULT_GOAL := help
.PHONY: run clean test help lint setup books cleanup install setup-scripts mongo

# Variables 
VENV_DIR = venv
PYTHON = $(VENV_DIR)/bin/python3
PIP = $(VENV_DIR)/bin/pip


run: $(VENV_DIR)/bin/activate
	$(PYTHON) -m flask --debug run

test: $(VENV_DIR)/bin/activate setup-scripts
	# Prepend virtualenv bin to PATH to use its Python and tools
	PATH=$(VENV_DIR)/bin:$$PATH ./scripts/run_tests.sh

lint: $(VENV_DIR)/bin/activate setup-scripts
	PATH=$(VENV_DIR)/bin:$$PATH ./scripts/run_pylint.sh

books: setup-scripts
	cd scripts && ./create_resources.sh

clean: setup-scripts
	cd scripts && ./delete_resources.sh

setup: clean books
	echo "Sample database setup complete."

mongo: setup-scripts
	cd scripts && ./start_mongodb.sh

help:
	@echo "Makefile commands:"
	@echo "  make install - Install virtual environment and dependencies."
	@echo "  make run     - Run Flask app."
	@echo "  make test    - Run tests and generates a coverage report."
	@echo "  make lint    - Runs the Pylint linter."
	@echo "  make books   - Populate the MongoDB collection with sample data."
	@echo "  make clean   - Remove all documents from the specified MongoDB collection."
	@echo "  make cleanup - Removes the virtual environment and cache files."
	@echo "  make help    - Shows this help message."

install: requirements.txt
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV_DIR) >/dev/null
	@echo "Installing dependencies..."
	${PIP} install -r requirements.txt >/dev/null 2>&1 || true
	@echo "Verifying installations..."
	$(PIP) list --format=freeze | diff - requirements.txt >/dev/null || $(PIP) install -r requirements.txt >/dev/null 2>&1
	@echo "Installation complete."

cleanup:
	rm -rf __pycache__
	rm -rf $(VENV_DIR)
	@echo "Cleaned up the project."

setup-scripts:
	chmod +x scripts/create_resources.sh
	chmod +x scripts/delete_resources.sh
	chmod +x scripts/run_pylint.sh
	chmod +x scripts/run_tests.sh