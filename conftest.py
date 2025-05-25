"""
Pytest configuration and fixtures for Budgetly application tests
"""
import pytest
import tempfile
import os
from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db
from models import User, Category, Rule, Transaction, Budget


@pytest.fixture(scope='function')
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Create app with test configuration
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "WTF_CSRF_ENABLED": False,  # Disable CSRF for easier testing
        "SECRET_KEY": "test-secret-key"
    })

    # Create the database and the database table
    with app.app_context():
        db.create_all()

    yield app

    # Clean up
    with app.app_context():
        db.session.remove()
        db.drop_all()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture
def test_user(app):
    """Create a test user and return the user ID."""
    with app.app_context():
        user = User(
            email='test@example.com',
            password_hash=generate_password_hash('testpassword123')
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge(user)  # Remove from session to prevent detached errors
        return user_id


@pytest.fixture
def test_user2(app):
    """Create a second test user for isolation testing and return the user ID."""
    with app.app_context():
        user = User(
            email='test2@example.com',
            password_hash=generate_password_hash('testpassword456')
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge(user)  # Remove from session to prevent detached errors
        return user_id


@pytest.fixture
def auth_client(client, test_user):
    """A test client with authenticated user."""
    # Login the test user
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'testpassword123'
    })
    # Verify login was successful
    assert response.status_code == 302  # Should redirect after login
    return client


@pytest.fixture
def test_category(app, test_user):
    """Create a test category and return the category ID."""
    with app.app_context():
        category = Category(name='Test Category', user_id=test_user)
        db.session.add(category)
        db.session.commit()
        category_id = category.id
        db.session.expunge(category)  # Remove from session to prevent detached errors
        return category_id


@pytest.fixture
def test_category_with_rules(app, test_user):
    """Create a test category with rules and return the category ID."""
    with app.app_context():
        category = Category(name='Groceries', user_id=test_user)
        db.session.add(category)
        db.session.flush()

        rule1 = Rule(keyword_pattern='walmart', category_id=category.id)
        rule2 = Rule(keyword_pattern='superstore', category_id=category.id)
        db.session.add(rule1)
        db.session.add(rule2)
        db.session.commit()
        category_id = category.id
        db.session.expunge_all()  # Remove all objects from session
        return category_id


@pytest.fixture
def test_transaction(app, test_user, test_category):
    """Create a test transaction and return the transaction ID."""
    with app.app_context():
        from datetime import date
        transaction = Transaction(
            date=date(2024, 12, 1),
            description='Test Transaction',
            amount=-50.00,
            account_source='Test Account',
            category_id=test_category,
            user_id=test_user
        )
        db.session.add(transaction)
        db.session.commit()
        transaction_id = transaction.id
        db.session.expunge(transaction)  # Remove from session to prevent detached errors
        return transaction_id


@pytest.fixture
def test_budget(app, test_user, test_category):
    """Create a test budget and return the budget ID."""
    with app.app_context():
        budget = Budget(
            category_id=test_category,
            month=12,
            year=2024,
            budgeted_amount=500.00,
            user_id=test_user
        )
        db.session.add(budget)
        db.session.commit()
        budget_id = budget.id
        db.session.expunge(budget)  # Remove from session to prevent detached errors
        return budget_id


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing file uploads."""
    return """Date,Description,Debit,Credit,Balance
2024-12-01,TEST GROCERY STORE,-25.50,,1000.00
2024-12-02,SALARY DEPOSIT,,2000.00,3000.00
"""


@pytest.fixture
def sample_csv_file(tmp_path, sample_csv_content):
    """Create a temporary CSV file for testing."""
    csv_file = tmp_path / "test_transactions.csv"
    csv_file.write_text(sample_csv_content)
    return str(csv_file)