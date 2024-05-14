SHELL := /bin/bash
# =============================================================================
# Variables
# =============================================================================

.DEFAULT_GOAL:=help
.ONESHELL:
ENV_PREFIX      := $(shell if [ -d .venv ]; then echo ".venv/bin/"; fi)
VENV_EXISTS     := $(shell if [ -d .venv ]; then echo "yes"; fi)

.EXPORT_ALL_VARIABLES:

.PHONY: help
help: 		   										## Display this help text for Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: install-pre-commit
install-pre-commit: 					## Install pre-commit and install hooks
	@echo "=> Installing pre-commit"
	@pre-commit install --install-hooks --all
	@pre-commit install --hook-type commit-msg
	@echo "=> pre-commit installed"

.PHONY: install-uv													## Install uv
install-uv:
	@if ! command -v uv &> /dev/null; then echo "=> Installing uv" && pipx install uv && echo "=> uv installed"; else echo "=> uv already installed"; fi

.PHONY: install
install: install-uv clean install-pre-commit ## Initialize project using uv (beta)
	@echo "=> Initializing project using uv ⚡️"
	@uv venv --seed -p python3.12
	@uv pip install -r requirements-test.txt
	@echo "=> Project initialized using uv (This does not include dev dependencies)"

.PHONY: destroy
destroy: ## Destroy the virtual environment
	rm -rf .venv

.PHONY: clean
clean: ## Autogenerated File Cleanup
	rm -rf .scannerwork/
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .hypothesis
	rm -rf build/
	rm -rf dist/
	rm -rf .eggs/
	find . -name '*.egg-info' -exec rm -rf {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '.ipynb_checkpoints' -exec rm -rf {} +
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf coverage.json
	rm -rf htmlcov/
	rm -rf .pytest_cache
	rm -rf tests/.pytest_cache
	rm -rf tests/**/.pytest_cache
	rm -rf .mypy_cache

.PHONY: lint
lint: ## Runs pre-commit hooks; includes ruff linting and formatting, codespell, type checking
	@pre-commit run --all-files
	@mypy .
