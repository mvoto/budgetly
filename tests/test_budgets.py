"""
Tests for budget management functionality
"""
import pytest
import json
from models import Budget, Category, User
from extensions import db


class TestBudgetAPI:
    """Test budget API endpoints."""

    def test_get_budgets_requires_login(self, client):
        """Test that get budgets API requires authentication."""
        response = client.get('/api/budgets/2024/12')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_get_budgets_success(self, app, auth_client, test_user):
        """Test successful retrieval of budgets."""
        # Create category and budget
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            budget = Budget(
                category_id=category.id,
                month=12,
                year=2024,
                budgeted_amount=500.00,
                user_id=test_user
            )
            db.session.add(budget)
            db.session.commit()

        response = auth_client.get('/api/budgets/2024/12')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) >= 1
        assert any(b['budgeted_amount'] == 500.00 for b in data)

    def test_get_budgets_empty_month(self, auth_client):
        """Test getting budgets for month with no budgets."""
        response = auth_client.get('/api/budgets/2024/1')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert len(data) == 0

    def test_set_budget_success(self, app, auth_client, test_user):
        """Test successful budget creation."""
        # Create a category first
        with app.app_context():
            category = Category(name='Budget Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 2024,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['budgeted_amount'] == 300.00
        assert data['month'] == 12
        assert data['year'] == 2024

    def test_update_existing_budget(self, app, auth_client, test_user):
        """Test updating an existing budget."""
        # Create category and budget first
        with app.app_context():
            category = Category(name='Update Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            budget = Budget(
                category_id=category.id,
                month=12,
                year=2024,
                budgeted_amount=200.00,
                user_id=test_user
            )
            db.session.add(budget)
            db.session.commit()
            category_id = category.id

        # Update the budget
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 2024,
            'budgeted_amount': 400.00
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['budgeted_amount'] == 400.00

    def test_set_budget_invalid_month_fails(self, app, auth_client, test_user):
        """Test that invalid month values are rejected."""
        # Create a category first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        # Test month 0
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 0,
            'year': 2024,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Month must be between 1 and 12' in data['error']

        # Test month 13
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 13,
            'year': 2024,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Month must be between 1 and 12' in data['error']

    def test_set_budget_invalid_year_fails(self, app, auth_client, test_user):
        """Test that invalid year values are rejected."""
        # Create a category first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        # Test year too low
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 1999,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Year must be between 2000 and 2100' in data['error']

        # Test year too high
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 2101,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Year must be between 2000 and 2100' in data['error']

    def test_set_budget_negative_amount_fails(self, app, auth_client, test_user):
        """Test that negative budget amounts are rejected."""
        # Create a category first
        with app.app_context():
            category = Category(name='Test Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 2024,
            'budgeted_amount': -100.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Budget amount cannot be negative' in data['error']

    def test_set_budget_nonexistent_category_fails(self, auth_client):
        """Test that setting budget for nonexistent category fails."""
        response = auth_client.post('/api/budgets', json={
            'category_id': 99999,  # Nonexistent category
            'month': 12,
            'year': 2024,
            'budgeted_amount': 300.0
        })
        assert response.status_code == 404
        assert b'Category not found' in response.data

    def test_delete_budget_success(self, app, auth_client, test_user):
        """Test successful budget deletion."""
        # Create category and budget first
        with app.app_context():
            category = Category(name='Delete Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            budget = Budget(
                category_id=category.id,
                month=12,
                year=2024,
                budgeted_amount=250.00,
                user_id=test_user
            )
            db.session.add(budget)
            db.session.commit()
            budget_id = budget.id

        response = auth_client.delete(f'/api/budgets/{budget_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'deleted successfully' in data['message']

        # Verify budget was deleted
        with app.app_context():
            deleted_budget = Budget.query.get(budget_id)
            assert deleted_budget is None

    def test_delete_nonexistent_budget_fails(self, auth_client):
        """Test that deleting nonexistent budget fails."""
        response = auth_client.delete('/api/budgets/99999')
        assert response.status_code == 404


class TestBudgetDataIsolation:
    """Test that users can only access their own budgets."""

    def test_user_can_only_see_own_budgets(self, app, auth_client, test_user, test_user2):
        """Test that users can only see their own budgets."""
        # Create categories and budgets for both users
        with app.app_context():
            cat1 = Category(name='User 1 Category', user_id=test_user)
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat1)
            db.session.add(cat2)
            db.session.flush()

            budget1 = Budget(
                category_id=cat1.id,
                month=12,
                year=2024,
                budgeted_amount=300.00,
                user_id=test_user
            )
            budget2 = Budget(
                category_id=cat2.id,
                month=12,
                year=2024,
                budgeted_amount=400.00,
                user_id=test_user2
            )
            db.session.add(budget1)
            db.session.add(budget2)
            db.session.commit()

        # User 1 should only see their budget
        response = auth_client.get('/api/budgets/2024/12')
        assert response.status_code == 200
        data = json.loads(response.data)
        budget_amounts = [b['budgeted_amount'] for b in data]
        assert 300.00 in budget_amounts
        assert 400.00 not in budget_amounts

    def test_user_cannot_access_other_user_budget(self, app, auth_client, test_user, test_user2):
        """Test that users cannot access other users' budgets."""
        # Create category and budget for user 2
        with app.app_context():
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat2)
            db.session.flush()

            budget2 = Budget(
                category_id=cat2.id,
                month=12,
                year=2024,
                budgeted_amount=500.00,
                user_id=test_user2
            )
            db.session.add(budget2)
            db.session.commit()
            budget2_id = budget2.id

        # User 1 should not be able to delete user 2's budget
        response = auth_client.delete(f'/api/budgets/{budget2_id}')
        assert response.status_code == 404

    def test_user_cannot_set_budget_for_other_user_category(self, app, auth_client, test_user, test_user2):
        """Test that users cannot set budgets for other users' categories."""
        # Create category for user 2
        with app.app_context():
            cat2 = Category(name='User 2 Category', user_id=test_user2)
            db.session.add(cat2)
            db.session.commit()
            cat2_id = cat2.id

        # User 1 should not be able to set budget for user 2's category
        response = auth_client.post('/api/budgets', json={
            'category_id': cat2_id,
            'month': 12,
            'year': 2024,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Category not found' in data['error']


class TestBudgetValidation:
    """Test budget validation logic."""

    def test_set_budget_missing_fields(self, auth_client):
        """Test that missing required fields are rejected."""
        # Missing category_id
        response = auth_client.post('/api/budgets', json={
            'month': 12,
            'year': 2024,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'category_id is required' in data['error']

        # Missing month
        response = auth_client.post('/api/budgets', json={
            'category_id': 1,
            'year': 2024,
            'budgeted_amount': 300.00
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'month is required' in data['error']

    def test_set_budget_zero_amount(self, app, auth_client, test_user):
        """Test that zero budget amount is allowed."""
        # Create a category first
        with app.app_context():
            category = Category(name='Zero Budget Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 2024,
            'budgeted_amount': 0.00
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['budgeted_amount'] == 0.00

    def test_budget_boundary_months(self, app, auth_client, test_user):
        """Test boundary values for months."""
        # Create a category first
        with app.app_context():
            category = Category(name='Boundary Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        # Test month 1 (valid)
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 1,
            'year': 2024,
            'budgeted_amount': 100.00
        })
        assert response.status_code == 201

        # Test month 12 (valid) - different month so it's a new budget
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 12,
            'year': 2024,
            'budgeted_amount': 200.00
        })
        assert response.status_code == 201  # New budget, not update

    def test_budget_boundary_years(self, app, auth_client, test_user):
        """Test boundary values for years."""
        # Create a category first
        with app.app_context():
            category = Category(name='Year Boundary Category', user_id=test_user)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        # Test year 2000 (valid)
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 1,
            'year': 2000,
            'budgeted_amount': 100.00
        })
        assert response.status_code == 201

        # Test year 2100 (valid)
        response = auth_client.post('/api/budgets', json={
            'category_id': category_id,
            'month': 2,
            'year': 2100,
            'budgeted_amount': 200.00
        })
        assert response.status_code == 201


class TestBudgetIntegration:
    """Test budget integration with other features."""

    def test_budget_with_category_deletion(self, app, auth_client, test_user):
        """Test that deleting category also deletes associated budgets."""
        # Create category and budget
        with app.app_context():
            category = Category(name='Category to Delete', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            budget = Budget(
                category_id=category.id,
                month=12,
                year=2024,
                budgeted_amount=350.00,
                user_id=test_user
            )
            db.session.add(budget)
            db.session.commit()
            category_id = category.id
            budget_id = budget.id

        # Delete the category
        response = auth_client.delete(f'/api/categories/{category_id}')
        assert response.status_code == 200

        # Verify budget was also deleted (cascade)
        with app.app_context():
            deleted_budget = Budget.query.get(budget_id)
            assert deleted_budget is None

    def test_budget_display_in_dashboard(self, app, auth_client, test_user):
        """Test that budgets are displayed in dashboard."""
        # Create category and budget
        with app.app_context():
            category = Category(name='Dashboard Category', user_id=test_user)
            db.session.add(category)
            db.session.flush()

            budget = Budget(
                category_id=category.id,
                month=12,
                year=2024,
                budgeted_amount=600.00,
                user_id=test_user
            )
            db.session.add(budget)
            db.session.commit()

        # Check dashboard shows budget information
        response = auth_client.get('/')
        assert response.status_code == 200
        # The dashboard should contain budget-related content
        assert b'Budget' in response.data or b'budget' in response.data