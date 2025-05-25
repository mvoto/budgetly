"""
Tests for transaction management functionality
"""
import pytest
from datetime import date
from models import Transaction, Category, User
from extensions import db


class TestTransactionViews:
    """Test transaction view access and authentication."""

    def test_dashboard_requires_authentication(self, client):
        """Test that dashboard requires authentication."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_transactions_page_requires_authentication(self, client):
        """Test that transactions page requires authentication."""
        response = client.get('/transactions')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_dashboard_loads_for_authenticated_user(self, auth_client):
        """Test that dashboard loads for authenticated user."""
        response = auth_client.get('/')
        assert response.status_code == 200
        assert b'Dashboard' in response.data

    def test_transactions_page_loads_for_authenticated_user(self, auth_client):
        """Test that transactions page loads for authenticated user."""
        response = auth_client.get('/transactions')
        assert response.status_code == 200
        assert b'Transactions' in response.data


class TestTransactionCRUD:
    """Test transaction CRUD operations."""

    def test_add_transaction_success(self, app, auth_client, test_user, test_category):
        """Test successful transaction addition."""
        response = auth_client.post('/add-transaction', data={
            'date': '2024-12-01',
            'description': 'Test Transaction',
            'amount': '-50.00',
            'account_source': 'Test Account',
            'category_id': test_category
        })

        assert response.status_code == 302
        assert '/' in response.location

        # Verify transaction was created
        with app.app_context():
            transaction = Transaction.query.filter_by(description='Test Transaction').first()
            assert transaction is not None
            assert transaction.amount == -50.00
            assert transaction.user_id == test_user

    def test_add_duplicate_transaction_fails(self, app, auth_client, test_user, test_category):
        """Test that duplicate transactions are rejected."""
        # Add first transaction
        auth_client.post('/add-transaction', data={
            'date': '2024-12-01',
            'description': 'Duplicate Transaction',
            'amount': '-25.00',
            'account_source': 'Test Account',
            'category_id': test_category
        })

        # Try to add duplicate
        response = auth_client.post('/add-transaction', data={
            'date': '2024-12-01',
            'description': 'Duplicate Transaction',
            'amount': '-25.00',
            'account_source': 'Test Account',
            'category_id': test_category
        })

        assert response.status_code == 200
        assert b'same description, amount, and date already exists' in response.data

    def test_edit_transaction_page_loads(self, app, auth_client, test_user, test_category):
        """Test that edit transaction page loads."""
        # Create a transaction first
        with app.app_context():
            transaction = Transaction(
                date=date(2024, 12, 1),
                description='Edit Test Transaction',
                amount=-30.00,
                account_source='Test Account',
                category_id=test_category,
                user_id=test_user
            )
            db.session.add(transaction)
            db.session.commit()
            transaction_id = transaction.id

        response = auth_client.get(f'/edit-transaction/{transaction_id}')
        assert response.status_code == 200
        assert b'Edit Transaction' in response.data

    def test_edit_transaction_success(self, app, auth_client, test_user, test_category):
        """Test successful transaction editing."""
        # Create a transaction first
        with app.app_context():
            transaction = Transaction(
                date=date(2024, 12, 1),
                description='Original Description',
                amount=-30.00,
                account_source='Test Account',
                category_id=test_category,
                user_id=test_user
            )
            db.session.add(transaction)
            db.session.commit()
            transaction_id = transaction.id

        # Edit the transaction
        response = auth_client.post(f'/edit-transaction/{transaction_id}', data={
            'date': '2024-12-02',
            'description': 'Updated Description',
            'amount': '-35.00',
            'account_source': 'Updated Account',
            'category_id': test_category
        })

        assert response.status_code == 302

        # Verify changes
        with app.app_context():
            updated_transaction = Transaction.query.get(transaction_id)
            assert updated_transaction.description == 'Updated Description'
            assert updated_transaction.amount == -35.00

    def test_delete_transaction_success(self, app, auth_client, test_user, test_category):
        """Test successful transaction deletion."""
        # Create a transaction first
        with app.app_context():
            transaction = Transaction(
                date=date(2024, 12, 1),
                description='Delete Test Transaction',
                amount=-40.00,
                account_source='Test Account',
                category_id=test_category,
                user_id=test_user
            )
            db.session.add(transaction)
            db.session.commit()
            transaction_id = transaction.id

        # Delete the transaction
        response = auth_client.post(f'/delete-transaction/{transaction_id}')
        assert response.status_code == 302

        # Verify deletion
        with app.app_context():
            deleted_transaction = Transaction.query.get(transaction_id)
            assert deleted_transaction is None

    def test_delete_all_transactions(self, app, auth_client, test_user, test_category):
        """Test deleting all transactions."""
        # Create multiple transactions
        with app.app_context():
            for i in range(3):
                transaction = Transaction(
                    date=date(2024, 12, i+1),
                    description=f'Transaction {i+1}',
                    amount=-(i+1)*10.00,
                    account_source='Test Account',
                    category_id=test_category,
                    user_id=test_user
                )
                db.session.add(transaction)
            db.session.commit()

        # Delete all transactions
        response = auth_client.post('/delete-all-transactions')
        assert response.status_code == 302

        # Verify all transactions are deleted
        with app.app_context():
            remaining_transactions = Transaction.query.filter_by(user_id=test_user).count()
            assert remaining_transactions == 0


class TestTransactionDataIsolation:
    """Test that users can only access their own transactions."""

    def test_user_can_only_see_own_transactions(self, app, auth_client, test_user, test_user2):
        """Test that users can only see their own transactions."""
        # Create transactions for both users using current month
        from datetime import date
        current_date = date.today()

        with app.app_context():
            # Transaction for user 1
            trans1 = Transaction(
                date=current_date,
                description='User 1 Transaction',
                amount=-25.00,
                account_source='User 1 Account',
                user_id=test_user
            )
            # Transaction for user 2
            trans2 = Transaction(
                date=current_date,
                description='User 2 Transaction',
                amount=-35.00,
                account_source='User 2 Account',
                user_id=test_user2
            )
            db.session.add(trans1)
            db.session.add(trans2)
            db.session.commit()

        # User 1 should only see their transaction
        response = auth_client.get('/transactions')
        assert response.status_code == 200
        assert b'User 1 Transaction' in response.data
        assert b'User 2 Transaction' not in response.data

    def test_api_transaction_isolation(self, app, auth_client, test_user, test_user2):
        """Test that API calls respect user isolation."""
        # Create categories for both users
        with app.app_context():
            cat1 = Category(name='User 1 Category', user_id=test_user)
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat1)
            db.session.add(cat2)
            db.session.commit()
            cat1_id = cat1.id
            cat2_id = cat2.id

        # Try to create transaction with other user's category
        response = auth_client.post('/add-transaction', data={
            'date': '2024-12-01',
            'description': 'Cross User Transaction',
            'amount': '-50.00',
            'account_source': 'Test Account',
            'category_id': cat2_id  # User 2's category
        })

        # Should succeed but category should be set to None
        assert response.status_code == 302  # Successful redirect
        with app.app_context():
            transaction = Transaction.query.filter_by(description='Cross User Transaction').first()
            assert transaction is not None
            assert transaction.user_id == test_user
            assert transaction.category_id is None  # Should be None due to invalid category


class TestTransactionSorting:
    """Test transaction sorting functionality."""

    def test_transaction_sorting_by_date(self, app, auth_client, test_user):
        """Test sorting transactions by date."""
        from datetime import date
        current_year = date.today().year
        current_month = date.today().month

        # Create multiple transactions with different dates in current month
        with app.app_context():
            transactions = [
                Transaction(date=date(current_year, current_month, 3), description='Third', amount=-30.00,
                          account_source='Test', user_id=test_user),
                Transaction(date=date(current_year, current_month, 1), description='First', amount=-10.00,
                          account_source='Test', user_id=test_user),
                Transaction(date=date(current_year, current_month, 2), description='Second', amount=-20.00,
                          account_source='Test', user_id=test_user),
            ]
            for trans in transactions:
                db.session.add(trans)
            db.session.commit()

        # Test sorting by date descending (default) for current month
        response = auth_client.get(f'/transactions/{current_year}/{current_month}?sort_by=date&sort_order=desc')
        assert response.status_code == 200
        content = response.data.decode()
        third_pos = content.find('Third')
        second_pos = content.find('Second')
        first_pos = content.find('First')
        # Should be in order: Third (latest), Second, First (earliest)
        assert third_pos > 0 and second_pos > 0 and first_pos > 0
        assert third_pos < second_pos < first_pos

    def test_transaction_sorting_by_amount(self, app, auth_client, test_user):
        """Test sorting transactions by amount."""
        from datetime import date
        current_year = date.today().year
        current_month = date.today().month

        # Create transactions with different amounts
        with app.app_context():
            transactions = [
                Transaction(date=date(current_year, current_month, 1), description='Medium', amount=-20.00,
                          account_source='Test', user_id=test_user),
                Transaction(date=date(current_year, current_month, 1), description='Smallest', amount=-10.00,
                          account_source='Test', user_id=test_user),
                Transaction(date=date(current_year, current_month, 1), description='Largest', amount=-30.00,
                          account_source='Test', user_id=test_user),
            ]
            for trans in transactions:
                db.session.add(trans)
            db.session.commit()

        # Test sorting by amount ascending for current month
        response = auth_client.get(f'/transactions/{current_year}/{current_month}?sort_by=amount&sort_order=asc')
        assert response.status_code == 200
        content = response.data.decode()
        largest_pos = content.find('Largest')
        medium_pos = content.find('Medium')
        smallest_pos = content.find('Smallest')
        # Should be in order: Largest (most negative), Medium, Smallest (least negative)
        assert largest_pos > 0 and medium_pos > 0 and smallest_pos > 0
        assert largest_pos < medium_pos < smallest_pos


class TestTransactionMonthNavigation:
    """Test month navigation functionality."""

    def test_specific_month_view(self, app, auth_client, test_user):
        """Test viewing transactions for a specific month."""
        # Create transactions in different months
        with app.app_context():
            trans_dec = Transaction(
                date=date(2024, 12, 1), description='December Transaction',
                amount=-25.00, account_source='Test', user_id=test_user)
            trans_nov = Transaction(
                date=date(2024, 11, 1), description='November Transaction',
                amount=-35.00, account_source='Test', user_id=test_user)
            db.session.add(trans_dec)
            db.session.add(trans_nov)
            db.session.commit()

        # View December transactions
        response = auth_client.get('/transactions/2024/12')
        assert response.status_code == 200
        assert b'December Transaction' in response.data
        assert b'November Transaction' not in response.data

        # View November transactions
        response = auth_client.get('/transactions/2024/11')
        assert response.status_code == 200
        assert b'November Transaction' in response.data
        assert b'December Transaction' not in response.data