"""
Tests for category management functionality
"""
import pytest
import json
from models import Category, Rule, User
from extensions import db


class TestCategoryViews:
    """Test category view access and authentication."""

    def test_category_manager_requires_authentication(self, client):
        """Test that category manager requires authentication."""
        response = client.get('/manage-categories')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_category_manager_loads_for_authenticated_user(self, auth_client):
        """Test that category manager loads for authenticated user."""
        response = auth_client.get('/manage-categories')
        assert response.status_code == 200
        assert b'Manage Categories' in response.data


class TestCategoryAPI:
    """Test category API endpoints."""

    def test_get_categories_success(self, app, auth_client, test_user):
        """Test successful retrieval of categories."""
        # Create a category for the user
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()

        response = auth_client.get('/api/categories')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) >= 1
        assert any(cat['name'] == 'Test Category' for cat in data)

    def test_add_category_success(self, auth_client):
        """Test successful category addition."""
        response = auth_client.post('/api/categories',
                                  json={'name': 'New Category'})
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == 'New Category'

    def test_add_category_duplicate_name_fails(self, app, auth_client, test_user):
        """Test that adding duplicate category name fails."""
        # Create a category first
        with app.app_context():
            category = Category(name='Duplicate Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()

        # Try to add duplicate
        response = auth_client.post('/api/categories',
                                  json={'name': 'Duplicate Category'})
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'already exists' in data['error']

    def test_add_category_case_insensitive_duplicate_fails(self, app, auth_client, test_user):
        """Test that category names are case insensitive for duplicates."""
        # Create a category first
        with app.app_context():
            category = Category(name='Case Test', user_id=test_user)
            db.session.add(category)
            db.session.commit()

        # Try to add with different case
        response = auth_client.post('/api/categories',
                                  json={'name': 'case test'})
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'already exists' in data['error']

    def test_add_category_empty_name_fails(self, auth_client):
        """Test that adding category with empty name fails."""
        response = auth_client.post('/api/categories',
                                  json={'name': ''})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Category name is required' in data['error']

    def test_update_category_success(self, app, auth_client, test_user):
        """Test successful category update."""
        # Create a category first
        with app.app_context():
            category = Category(name='Original Name', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.put(f'/api/categories/{category_id}',
                                 json={'name': 'Updated Name'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'Updated Name'

    def test_update_category_empty_name_fails(self, app, auth_client, test_user):
        """Test that updating category with empty name fails."""
        # Create a category first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.put(f'/api/categories/{category_id}',
                                 json={'name': ''})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'New category name is required and cannot be empty' in data['error']

    def test_delete_category_success(self, app, auth_client, test_user):
        """Test successful category deletion."""
        # Create a category first
        with app.app_context():
            category = Category(name='Delete Me', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.delete(f'/api/categories/{category_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'deleted successfully' in data['message']

        # Verify category was deleted
        with app.app_context():
            deleted_category = Category.query.get(category_id)
            assert deleted_category is None


class TestCategoryDataIsolation:
    """Test that users can only access their own categories."""

    def test_user_can_only_see_own_categories(self, app, auth_client, test_user, test_user2):
        """Test that users can only see their own categories."""
        # Create categories for both users
        with app.app_context():
            cat1 = Category(name='User 1 Category', user_id=test_user)
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat1)
            db.session.add(cat2)
            db.session.commit()

        # User 1 should only see their categories
        response = auth_client.get('/api/categories')
        assert response.status_code == 200
        data = json.loads(response.data)
        category_names = [cat['name'] for cat in data]
        assert 'User 1 Category' in category_names
        assert 'User 2 Category' not in category_names

    def test_user_cannot_access_other_user_category(self, app, auth_client, test_user, test_user2):
        """Test that users cannot access other users' categories."""
        # Create category for user 2
        with app.app_context():
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat2)
            db.session.commit()
            cat2_id = cat2.id

        # User 1 should not be able to update user 2's category
        response = auth_client.put(f'/api/categories/{cat2_id}',
                                 json={'name': 'Hacked Name'})
        assert response.status_code == 404

        # User 1 should not be able to delete user 2's category
        response = auth_client.delete(f'/api/categories/{cat2_id}')
        assert response.status_code == 404


class TestCategoryRules:
    """Test category rule management."""

    def test_add_rule_to_category_success(self, app, auth_client, test_user):
        """Test successful rule addition to category."""
        # Create a category first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.post(f'/api/categories/{category_id}/rules',
                                  json={'keyword_pattern': 'test keyword'})
        assert response.status_code == 201
        data = json.loads(response.data)
        # Response is category.to_dict() which includes rules
        assert 'rules' in data
        assert len(data['rules']) == 1
        assert data['rules'][0]['keyword_pattern'] == 'test keyword'

    def test_add_rule_empty_keyword_fails(self, app, auth_client, test_user):
        """Test that adding rule with empty keyword fails."""
        # Create a category first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.post(f'/api/categories/{category_id}/rules',
                                  json={'keyword_pattern': ''})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Keyword pattern is required' in data['error']

    def test_add_duplicate_rule_fails(self, app, auth_client, test_user):
        """Test that adding duplicate rule fails."""
        # Create a category with a rule first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()
            rule = Rule(keyword_pattern='duplicate', category_id=category.id)
            db.session.add(rule)
            db.session.commit()
            category_id = category.id

        # Try to add duplicate rule
        response = auth_client.post(f'/api/categories/{category_id}/rules',
                                  json={'keyword_pattern': 'duplicate'})
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'already exists' in data['error']

    def test_update_rule_success(self, app, auth_client, test_user):
        """Test successful rule update."""
        # Create a category with a rule first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()
            rule = Rule(keyword_pattern='original', category_id=category.id)
            db.session.add(rule)
            db.session.commit()
            rule_id = rule.id

        response = auth_client.put(f'/api/rules/{rule_id}',
                                 json={'keyword_pattern': 'updated'})
        assert response.status_code == 200
        data = json.loads(response.data)
        # Response is category.to_dict() which includes rules
        assert 'rules' in data
        assert len(data['rules']) == 1
        assert data['rules'][0]['keyword_pattern'] == 'updated'

    def test_update_rule_empty_keyword_fails(self, app, auth_client, test_user):
        """Test that updating rule with empty keyword fails."""
        # Create a category with a rule first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()
            rule = Rule(keyword_pattern='original', category_id=category.id)
            db.session.add(rule)
            db.session.commit()
            rule_id = rule.id

        response = auth_client.put(f'/api/rules/{rule_id}',
                                 json={'keyword_pattern': ''})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'New keyword pattern is required and cannot be empty' in data['error']

    def test_delete_rule_success(self, app, auth_client, test_user):
        """Test successful rule deletion."""
        # Create a category with a rule first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()
            rule = Rule(keyword_pattern='delete me', category_id=category.id)
            db.session.add(rule)
            db.session.commit()
            rule_id = rule.id

        response = auth_client.delete(f'/api/rules/{rule_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Response is category.to_dict() which should now have empty rules
        assert 'rules' in data
        assert len(data['rules']) == 0

        # Verify rule was deleted
        with app.app_context():
            deleted_rule = Rule.query.get(rule_id)
            assert deleted_rule is None

    def test_user_cannot_access_other_user_rules(self, app, auth_client, test_user, test_user2):
        """Test that users cannot access rules from other users' categories."""
        # Create category and rule for user 2
        with app.app_context():
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat2)
            db.session.flush()
            rule2 = Rule(keyword_pattern='user2 rule', category_id=cat2.id)
            db.session.add(rule2)
            db.session.commit()
            rule2_id = rule2.id

        # User 1 should not be able to update user 2's rule
        response = auth_client.put(f'/api/rules/{rule2_id}',
                                 json={'keyword_pattern': 'hacked'})
        assert response.status_code == 403

        # User 1 should not be able to delete user 2's rule
        response = auth_client.delete(f'/api/rules/{rule2_id}')
        assert response.status_code == 403


class TestDefaultCategories:
    """Test default category creation."""

    def test_add_default_categories_success(self, auth_client):
        """Test successful addition of default categories."""
        response = auth_client.post('/api/add-default-categories')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Default categories added successfully' in data['message']

        # Verify categories were created
        response = auth_client.get('/api/categories')
        assert response.status_code == 200
        categories = json.loads(response.data)
        assert len(categories) > 0
        category_names = [cat['name'] for cat in categories]
        assert 'Groceries' in category_names
        assert 'Dining Out/Cafe' in category_names

    def test_add_default_categories_when_categories_exist_fails(self, app, auth_client, test_user):
        """Test that adding default categories fails when user already has categories."""
        # Create a category first
        with app.app_context():
            category = Category(name='Existing Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()

        response = auth_client.post('/api/add-default-categories')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'already has categories' in data['error']


class TestCategoryIntegration:
    """Test category integration with other features."""

    def test_category_with_transactions_deletion(self, app, auth_client, test_user):
        """Test that deleting category with transactions works correctly."""
        from models import Transaction
        from datetime import date

        # Create category and transaction
        with app.app_context():
            category = Category(name='Category with Transactions', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            transaction = Transaction(
                date=date(2024, 12, 1),
                description='Test Transaction',
                amount=-50.00,
                account_source='Test Account',
                category_id=category.id,
                user_id=test_user
            )
            db.session.add(transaction)
            db.session.commit()
            category_id = category.id
            transaction_id = transaction.id

        # Delete the category
        response = auth_client.delete(f'/api/categories/{category_id}')
        assert response.status_code == 200

        # Verify category was deleted and transaction category was set to None
        with app.app_context():
            deleted_category = Category.query.get(category_id)
            assert deleted_category is None

            updated_transaction = Transaction.query.get(transaction_id)
            assert updated_transaction is not None
            assert updated_transaction.category_id is None