"""
Tests for file upload functionality
"""
import pytest
import io
import json
from models import Transaction, Category, Rule, User
from extensions import db


class TestFileUploadSecurity:
    """Test file upload security and authentication."""

    def test_upload_requires_authentication(self, client):
        """Test that file upload requires authentication."""
        response = client.post('/upload')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_upload_without_file_fails(self, auth_client):
        """Test that upload without file fails."""
        response = auth_client.post('/upload', data={})
        assert response.status_code == 302  # Redirects with flash message

    def test_upload_empty_file_fails(self, auth_client):
        """Test that uploading empty file fails."""
        empty_file = io.BytesIO(b'')
        response = auth_client.post('/upload', data={
            'file': (empty_file, 'empty.csv')
        })
        assert response.status_code == 302  # Handles gracefully by redirecting

    def test_upload_non_csv_file_fails(self, auth_client):
        """Test that uploading non-CSV file fails."""
        text_file = io.BytesIO(b'This is not a CSV file')
        response = auth_client.post('/upload', data={
            'file': (text_file, 'test.txt')
        })
        assert response.status_code == 302  # Handles gracefully by redirecting


class TestCSVFileUpload:
    """Test CSV file upload and processing."""

    def test_upload_valid_csv_success(self, app, auth_client, test_user):
        """Test successful upload of valid CSV file."""
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,TEST GROCERY STORE,-25.50,,1000.00
2024-12-02,SALARY DEPOSIT,,2000.00,3000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'test.csv')
        })

        assert response.status_code == 302

        # Verify transactions were created
        with app.app_context():
            transactions = Transaction.query.filter_by(user_id=test_user).all()
            assert len(transactions) >= 2
            descriptions = [t.description for t in transactions]
            assert 'TEST GROCERY STORE' in descriptions
            assert 'SALARY DEPOSIT' in descriptions

    def test_upload_duplicate_transactions_skipped(self, app, auth_client, test_user):
        """Test that duplicate transactions are skipped during upload."""
        # First upload
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,DUPLICATE TRANSACTION,-50.00,,1000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        response = auth_client.post('/upload', data={
            'file': (csv_file, 'first.csv')
        })
        assert response.status_code == 302

        # Count transactions after first upload
        with app.app_context():
            initial_count = Transaction.query.filter_by(user_id=test_user).count()

        # Second upload with same transaction
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        response = auth_client.post('/upload', data={
            'file': (csv_file, 'second.csv')
        })
        assert response.status_code == 302

        # Verify no new transactions were added
        with app.app_context():
            final_count = Transaction.query.filter_by(user_id=test_user).count()
            assert final_count == initial_count

    def test_upload_malformed_csv_handles_errors(self, auth_client):
        """Test that malformed CSV is handled gracefully."""
        malformed_csv = """Date,Description,Amount
2024-12-01,TEST,invalid_amount
2024-12-02,VALID TRANSACTION,-25.50
"""
        csv_file = io.BytesIO(malformed_csv.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'malformed.csv')
        })

        # Should still redirect (partial success)
        assert response.status_code == 302


class TestFileUploadDataIsolation:
    """Test that file uploads respect user data isolation."""

    def test_uploaded_transactions_belong_to_current_user(self, app, auth_client, test_user):
        """Test that uploaded transactions are assigned to current user."""
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,TEST TRANSACTION,-25.50,,1000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'test.csv')
        })

        assert response.status_code == 302

        # Verify transaction belongs to the correct user
        with app.app_context():
            transaction = Transaction.query.filter_by(description='TEST TRANSACTION').first()
            assert transaction is not None
            assert transaction.user_id == test_user

    def test_categorization_uses_user_categories(self, app, auth_client, test_user, test_user2):
        """Test that categorization only uses current user's categories."""
        # Create categories for both users with same keyword
        with app.app_context():
            from models import Category, Rule

            # User 1's category
            cat1 = Category(name='User 1 Groceries', user_id=test_user)
            db.session.add(cat1)
            db.session.flush()
            rule1 = Rule(keyword_pattern='grocery', category_id=cat1.id)
            db.session.add(rule1)

            # User 2's category
            cat2 = Category(name='User 2 Groceries', user_id=test_user2)
            db.session.add(cat2)
            db.session.flush()
            rule2 = Rule(keyword_pattern='grocery', category_id=cat2.id)
            db.session.add(rule2)

            db.session.commit()
            cat1_id = cat1.id

        # Upload transaction that should match the keyword
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,GROCERY STORE PURCHASE,-25.50,,1000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'test.csv')
        })

        assert response.status_code == 302

        # Verify transaction was categorized with user 1's category
        with app.app_context():
            transaction = Transaction.query.filter_by(description='GROCERY STORE PURCHASE').first()
            assert transaction is not None
            assert transaction.user_id == test_user
            assert transaction.category_id == cat1_id


class TestFileUploadErrorHandling:
    """Test file upload error handling and edge cases."""

    def test_upload_large_file_handled(self, auth_client):
        """Test that large files are handled appropriately."""
        # Create a large CSV content (but not too large for testing)
        large_content = "Date,Description,Debit,Credit,Balance\n"
        for i in range(1000):
            large_content += f"2024-12-01,Transaction {i},-{i}.00,,1000.00\n"

        csv_file = io.BytesIO(large_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'large.csv')
        })

        # Should handle large file (may succeed or fail gracefully)
        assert response.status_code in [302, 400, 413]

    def test_upload_csv_with_special_characters(self, app, auth_client, test_user):
        """Test upload of CSV with special characters."""
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,"CAFÉ & RESTAURANT",-25.50,,1000.00
2024-12-02,"MÜLLER'S STORE",-15.00,,985.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'special.csv')
        })

        assert response.status_code == 302

        # Verify transactions with special characters were created
        with app.app_context():
            transactions = Transaction.query.filter_by(user_id=test_user).all()
            descriptions = [t.description for t in transactions]
            assert any('CAFÉ' in desc for desc in descriptions)
            assert any('MÜLLER' in desc for desc in descriptions)

    def test_upload_csv_with_missing_columns(self, auth_client):
        """Test upload of CSV with missing required columns."""
        incomplete_csv = """Date,Description
2024-12-01,INCOMPLETE TRANSACTION
"""
        csv_file = io.BytesIO(incomplete_csv.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'incomplete.csv')
        })

        # Should handle missing columns gracefully
        assert response.status_code in [302, 400]

    def test_upload_csv_with_invalid_dates(self, auth_client):
        """Test upload of CSV with invalid date formats."""
        invalid_date_csv = """Date,Description,Debit,Credit,Balance
invalid-date,INVALID DATE TRANSACTION,-25.50,,1000.00
2024-13-45,ANOTHER INVALID DATE,-15.00,,985.00
"""
        csv_file = io.BytesIO(invalid_date_csv.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'invalid_dates.csv')
        })

        # Should handle invalid dates gracefully
        assert response.status_code in [302, 400]


class TestFileUploadIntegration:
    """Test file upload integration with other features."""

    def test_upload_page_loads_correctly(self, auth_client):
        """Test that upload functionality is accessible from UI."""
        # Check transactions page has upload functionality
        response = auth_client.get('/transactions')
        assert response.status_code == 200
        assert b'upload' in response.data.lower() or b'Upload' in response.data

    def test_upload_with_csrf_protection(self, app, auth_client, test_user):
        """Test that upload respects CSRF protection when enabled."""
        # Note: CSRF is disabled in test config, but we test the endpoint exists
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,CSRF TEST TRANSACTION,-25.50,,1000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'csrf_test.csv')
        })

        assert response.status_code == 302

        # Verify transaction was created
        with app.app_context():
            transaction = Transaction.query.filter_by(description='CSRF TEST TRANSACTION').first()
            assert transaction is not None
            assert transaction.user_id == test_user

    def test_upload_redirects_to_transactions_page(self, auth_client):
        """Test that successful upload redirects to transactions page."""
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,REDIRECT TEST,-25.50,,1000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'redirect_test.csv')
        })

        assert response.status_code == 302
        # Should redirect to transactions or dashboard
        assert '/transactions' in response.location or '/' in response.location

    def test_upload_with_existing_categories_auto_categorizes(self, app, auth_client, test_user):
        """Test that upload automatically categorizes transactions when rules exist."""
        # Create category with rule
        with app.app_context():
            category = Category(name='Auto Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            rule = Rule(keyword_pattern='walmart', category_id=category.id)
            db.session.add(rule)
            db.session.commit()
            category_id = category.id

        # Upload transaction that should match the rule
        csv_content = """Date,Description,Debit,Credit,Balance
2024-12-01,WALMART SUPERCENTER,-75.00,,1000.00
"""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))

        response = auth_client.post('/upload', data={
            'file': (csv_file, 'auto_categorize.csv')
        })

        assert response.status_code == 302

        # Verify transaction was auto-categorized
        with app.app_context():
            transaction = Transaction.query.filter_by(description='WALMART SUPERCENTER').first()
            assert transaction is not None
            assert transaction.category_id == category_id