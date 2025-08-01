# Makefile for Telegram Bot Development

.PHONY: help install install-dev test lint format type-check security-check run clean docker-build docker-run

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt -r requirements-dev.txt

test: ## Run tests
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term

lint: ## Run linting
	ruff check .
	black --check .

format: ## Format code
	black .
	ruff check --fix .

type-check: ## Run type checking
	mypy working_bot.py services/ bot/

security-check: ## Check for security vulnerabilities
	pip-audit
	safety check

run: ## Run the bot locally
	python working_bot.py

run-dev: ## Run bot in development mode with auto-reload
	python -m watchdog.observers working_bot.py

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache htmlcov .coverage .mypy_cache

webhook-test: ## Test webhook locally with ngrok
	@echo "Start ngrok in another terminal: ngrok http 8443"
	@echo "Then set webhook: curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook -d url=https://<YOUR_NGROK_URL>/webhook"

docker-build: ## Build Docker image
	docker build -t mintoctopus-bot .

docker-run: ## Run bot in Docker
	docker run --env-file .env -v $(PWD)/data:/app/data mintoctopus-bot

check-all: install-dev lint type-check security-check test ## Run all checks

pre-commit: format lint type-check ## Run pre-commit checks

deploy-check: ## Check if ready for deployment
	@echo "🔍 Deployment readiness check:"
	@python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅ BOT_TOKEN set' if os.getenv('BOT_TOKEN') else '❌ BOT_TOKEN missing')"
	@python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅ OPENAI_API_KEY set' if os.getenv('OPENAI_API_KEY') else '❌ OPENAI_API_KEY missing')"
	@test -f data/database.json && echo "✅ Database file exists" || echo "❌ Database file missing"
	@python3 -c "import json; data=json.load(open('data/database.json')); print(f'✅ {len(data.get(\"masters\", []))} masters in database')"