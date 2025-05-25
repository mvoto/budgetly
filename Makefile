.PHONY: test test-verbose test-coverage test-auth test-transactions test-categories test-budgets test-upload clean install dev

# Install dependencies
install:
	pip install -r requirements.txt

# Run all tests
test:
	pytest

# Run tests with verbose output
test-verbose:
	pytest -v

# Run tests with coverage report
test-coverage:
	pytest --cov=app --cov=models --cov=extensions --cov=auth --cov=categorizer --cov=parser --cov-report=term-missing --cov-report=html:htmlcov

# Run specific test modules
test-auth:
	pytest tests/test_auth.py -v

test-transactions:
	pytest tests/test_transactions.py -v

test-categories:
	pytest tests/test_categories.py -v

test-budgets:
	pytest tests/test_budgets.py -v

test-upload:
	pytest tests/test_file_upload.py -v

# Run application in development mode
dev:
	python app.py

# Clean up test artifacts
clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run tests and open coverage report
test-and-coverage: test-coverage
	open htmlcov/index.html