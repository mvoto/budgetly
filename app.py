from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename # For securely saving filenames
from datetime import datetime, date, timedelta # Ensure timedelta is imported
from collections import defaultdict # For calculating category sums
import json # For passing data to JavaScript
import calendar # For month names
from sqlalchemy import extract # For filtering by month/year
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # For database migrations
import logging # For better logging
from flask_login import login_required, current_user

from extensions import db, login_manager, csrf
from models import Category, Rule, Transaction, Budget, User
from categorizer import assign_category, get_defined_categories
from parser import process_uploaded_file # Re-adding parser for file uploads
from auth import auth

load_dotenv() # Load environment variables from .env

# Setup basic logging
logging.basicConfig(level=logging.INFO)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def create_default_categories_for_user(user_id):
    """Helper function to create default categories for a new user."""
    from models import Category, Rule
    from extensions import db

    # Define which categories should be marked as fixed costs
    fixed_cost_categories = {
        "Bills/Utilities",
        "Insurance",
        "Housing"
    }

    default_categories_rules = {
        "Groceries": ["superstore", "save on foods", "wal-mart groceries"],
        "Dining Out/Cafe": ["mcdonald's", "tim hortons", "starbucks", "subway", "pizza"],
        "Food Delivery": ["uber eats", "doordash", "skipTheDishes"],
        "Bills/Utilities": ["fido mobile", "fortisbc energy", "hydro"],
        "Subscriptions/Entertainment": ["netflix.com", "spotify", "disney plus"],
        "Subscriptions/Services": ["apple.com/bill", "google cloud"],
        "Shopping/Online": ["amazon.ca", "temu.com", "ebay"],
        "Shopping/General Merchandise": ["wal-mart", "dollarama", "winners"],
        "Healthcare": ["pharmacy", "clinic", "dental"],
        "Insurance": ["icbc", "square one insurance", "life insurance"],
        "Car": ["gas station", "esso", "shell", "petro-canada", "mechanic", "car wash"],
        "Investments": ["questrade", "wealthsimple"],
        "Transfers": ["e-transfer", "send money"],
        "Credit Card Payment": ["payment - thank you", "cibc visa payment", "td mc payment"],
        "Housing": ["rent", "mortgage", "strata fee"],
        "Childcare/Education": ["daycare", "school fees"],
        "Therapy": [],
        "Travel": ["expedia", "booking.com", "airbnb", "flights"],
        "Miscellaneous": ["misc", "other"]
    }

    for cat_name, rules_list in default_categories_rules.items():
        is_fixed_cost = cat_name in fixed_cost_categories
        category = Category(name=cat_name, user_id=user_id, is_fixed_cost=is_fixed_cost)
        db.session.add(category)
        db.session.flush()
        for rule_kw in rules_list:
            rule = Rule(keyword_pattern=rule_kw, category_id=category.id)
            db.session.add(rule)
    db.session.commit()

def create_app():
    app = Flask(__name__, template_folder='templates')

    # --- Configuration ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_strong_default_secret_key_pls_change')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///categories_rules.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

    # Ensure upload folder exists and has correct permissions
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'], mode=0o755)
        app.logger.info(f"Created uploads directory: {app.config['UPLOAD_FOLDER']}")

    # --- Initialize Extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    Migrate(app, db)

    # Register blueprints
    app.register_blueprint(auth)

    # --- Routes ---
    @app.route('/')
    @app.route('/<int:year>/<int:month>')
    @login_required
    def home(year=None, month=None):
        # Get sorting parameters from URL
        sort_by = request.args.get('sort_by', 'date')  # Default sort by date
        sort_order = request.args.get('sort_order', 'desc')  # Default descending order

        # Validate sort_by parameter to prevent SQLAlchemy errors
        valid_columns = ['date', 'description', 'amount', 'account_source', 'category']
        if sort_by not in valid_columns:
            sort_by = 'date'

        # Validate sort_order parameter
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        # Use provided year/month or default to current month
        today = date.today()
        if year is None or month is None:
            year = today.year
            month = today.month

        # Validate month and year
        if month < 1 or month > 12:
            month = today.month
            year = today.year

        # Calculate start and end dates for the specified month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        # Build the query with sorting
        query = Transaction.query.filter(
            Transaction.date >= start_date,
            Transaction.date < end_date,
            Transaction.user_id == current_user.id
        )

        # Apply sorting based on column
        if sort_by == 'date':
            if sort_order == 'asc':
                query = query.order_by(Transaction.date.asc())
            else:
                query = query.order_by(Transaction.date.desc())
        elif sort_by == 'description':
            if sort_order == 'asc':
                query = query.order_by(Transaction.description.asc())
            else:
                query = query.order_by(Transaction.description.desc())
        elif sort_by == 'amount':
            if sort_order == 'asc':
                query = query.order_by(Transaction.amount.asc())
            else:
                query = query.order_by(Transaction.amount.desc())
        elif sort_by == 'account_source':
            if sort_order == 'asc':
                query = query.order_by(Transaction.account_source.asc())
            else:
                query = query.order_by(Transaction.account_source.desc())
        elif sort_by == 'category':
            # For category sorting, we need to join with Category table
            from sqlalchemy import func
            if sort_order == 'asc':
                query = query.outerjoin(Category).order_by(func.coalesce(Category.name, 'Uncategorized').asc())
            else:
                query = query.outerjoin(Category).order_by(func.coalesce(Category.name, 'Uncategorized').desc())

        transactions = query.all()

        # Calculate totals by category
        category_totals = defaultdict(float)
        expense_categories = defaultdict(float)

        for transaction in transactions:
            category_name = transaction.category.name if transaction.category else 'Uncategorized'
            category_totals[category_name] += transaction.amount

            # Only track expenses for charts (negative amounts)
            if transaction.amount < 0:
                expense_categories[category_name] += abs(transaction.amount)  # Convert to positive for chart

        # Calculate income and expenses
        total_income = sum(amount for amount in (t.amount for t in transactions) if amount > 0)
        total_expenses = sum(amount for amount in (t.amount for t in transactions) if amount < 0)
        net_amount = total_income + total_expenses  # expenses are negative

        # Prepare chart data for JavaScript
        expense_chart_data = {
            'labels': list(expense_categories.keys()),
            'data': list(expense_categories.values())
        }

        # Prepare bar chart data (Income vs Expenses)
        bar_chart_data = {
            'labels': ['Income', 'Expenses'],
            'data': [total_income, abs(total_expenses)]
        }

        # Get top 5 spending categories
        top_spending_categories = sorted(
            expense_categories.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Calculate navigation dates (previous and next month)
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year

        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        # Get budget data for the current month
        budgets = Budget.query.filter_by(month=month, year=year, user_id=current_user.id).all()
        budget_data = {}
        total_budgeted = 0
        total_spent = 0

        # Create a mapping of budget data
        for budget in budgets:
            if budget.category:
                category_name = budget.category.name
                # Get actual spending for this category (only expenses, so negative amounts)
                actual_spent = abs(category_totals.get(category_name, 0)) if category_totals.get(category_name, 0) < 0 else 0

                budget_data[category_name] = {
                    'budgeted': budget.budgeted_amount,
                    'spent': actual_spent,
                    'remaining': budget.budgeted_amount - actual_spent,
                    'percentage': (actual_spent / budget.budgeted_amount * 100) if budget.budgeted_amount > 0 else 0,
                    'over_budget': actual_spent > budget.budgeted_amount
                }

                total_budgeted += budget.budgeted_amount
                total_spent += actual_spent

        # Calculate overall budget performance
        budget_summary = {
            'total_budgeted': total_budgeted,
            'total_spent': total_spent,
            'total_remaining': total_budgeted - total_spent,
            'overall_percentage': (total_spent / total_budgeted * 100) if total_budgeted > 0 else 0,
            'over_budget': total_spent > total_budgeted
        }

        # Get all categories for budget setup
        all_categories = [category.to_dict() for category in Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()]

        return render_template('index.html',
                            transactions=transactions,
                            category_totals=dict(category_totals),
                            total_income=total_income,
                            total_expenses=abs(total_expenses),
                            net_amount=net_amount,
                            current_month=calendar.month_name[month],
                            current_year=year,
                            current_month_num=month,
                            current_sort_by=sort_by,
                            current_sort_order=sort_order,
                            expense_chart_data=json.dumps(expense_chart_data),
                            bar_chart_data=json.dumps(bar_chart_data),
                            top_spending_categories=top_spending_categories,
                            prev_month=prev_month,
                            prev_year=prev_year,
                            next_month=next_month,
                            next_year=next_year,
                            is_current_month=(year == today.year and month == today.month),
                            month_names=calendar.month_name,
                            budget_data=budget_data,
                            budget_summary=budget_summary,
                            all_categories=all_categories)

    @app.route('/transactions')
    @app.route('/transactions/<int:year>/<int:month>')
    @login_required
    def transactions(year=None, month=None):
        # Get sorting parameters from URL
        sort_by = request.args.get('sort_by', 'date')  # Default sort by date
        sort_order = request.args.get('sort_order', 'desc')  # Default descending order

        # Validate sort_by parameter to prevent SQLAlchemy errors
        valid_columns = ['date', 'description', 'amount', 'account_source', 'category']
        if sort_by not in valid_columns:
            sort_by = 'date'

        # Validate sort_order parameter
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        # Use provided year/month or default to current month
        today = date.today()
        if year is None or month is None:
            year = today.year
            month = today.month

        # Validate month and year
        if month < 1 or month > 12:
            month = today.month
            year = today.year

        # Calculate start and end dates for the specified month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        # Build the query with sorting
        query = Transaction.query.filter(
            Transaction.date >= start_date,
            Transaction.date < end_date,
            Transaction.user_id == current_user.id
        )

        # Apply sorting based on column
        if sort_by == 'date':
            if sort_order == 'asc':
                query = query.order_by(Transaction.date.asc())
            else:
                query = query.order_by(Transaction.date.desc())
        elif sort_by == 'description':
            if sort_order == 'asc':
                query = query.order_by(Transaction.description.asc())
            else:
                query = query.order_by(Transaction.description.desc())
        elif sort_by == 'amount':
            if sort_order == 'asc':
                query = query.order_by(Transaction.amount.asc())
            else:
                query = query.order_by(Transaction.amount.desc())
        elif sort_by == 'account_source':
            if sort_order == 'asc':
                query = query.order_by(Transaction.account_source.asc())
            else:
                query = query.order_by(Transaction.account_source.desc())
        elif sort_by == 'category':
            # For category sorting, we need to join with Category table
            from sqlalchemy import func
            if sort_order == 'asc':
                query = query.outerjoin(Category).order_by(func.coalesce(Category.name, 'Uncategorized').asc())
            else:
                query = query.outerjoin(Category).order_by(func.coalesce(Category.name, 'Uncategorized').desc())

        transactions = query.all()

        # Calculate navigation dates (previous and next month)
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year

        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        return render_template('transactions.html',
                            transactions=transactions,
                            current_month=calendar.month_name[month],
                            current_year=year,
                            current_month_num=month,
                            current_sort_by=sort_by,
                            current_sort_order=sort_order,
                            prev_month=prev_month,
                            prev_year=prev_year,
                            next_month=next_month,
                            next_year=next_year,
                            is_current_month=(year == today.year and month == today.month),
                            month_names=calendar.month_name)

    @app.route('/upload', methods=['POST'])
    @login_required
    def upload_file():
        if 'file' not in request.files:
            app.logger.warning("No file part in request")
            flash('No file part', 'error')
            return redirect(url_for('transactions'))

        file = request.files['file']
        if file.filename == '':
            app.logger.warning("No selected file")
            flash('No selected file', 'error')
            return redirect(url_for('transactions'))

        if file:
            try:
                # Ensure upload folder exists (in case it was deleted)
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'], mode=0o755)
                    app.logger.info(f"Re-created uploads directory: {app.config['UPLOAD_FOLDER']}")

                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                app.logger.info(f"Saving uploaded file: {filename} to {filepath}")
                file.save(filepath)

                if not os.path.exists(filepath):
                    app.logger.error(f"File was not saved successfully: {filepath}")
                    flash('Error saving file', 'error')
                    return redirect(url_for('transactions'))

                app.logger.info(f"File saved successfully, size: {os.path.getsize(filepath)} bytes")

                try:
                    app.logger.info(f"Processing file: {filename}")
                    transactions = process_uploaded_file(filepath, filename, current_user.id)
                    app.logger.info(f"Found {len(transactions)} transactions to add")

                    if transactions:
                        added_count = 0
                        duplicate_count = 0

                        for transaction in transactions:
                            # Set the user_id for the transaction
                            transaction.user_id = current_user.id

                            # Check for duplicate transactions with same description, amount, and date for this user
                            existing_transaction = Transaction.query.filter_by(
                                description=transaction.description,
                                amount=transaction.amount,
                                date=transaction.date,
                                user_id=current_user.id
                            ).first()

                            if existing_transaction:
                                duplicate_count += 1
                                app.logger.debug(f"Skipping duplicate transaction: {transaction.description}, {transaction.amount}, {transaction.date}")
                            else:
                                app.logger.debug(f"Adding transaction: {transaction.description}, {transaction.amount}, {transaction.category_id}")
                                db.session.add(transaction)
                                added_count += 1

                        db.session.commit()

                        if duplicate_count > 0:
                            app.logger.info(f"Successfully added {added_count} new transactions, skipped {duplicate_count} duplicates")
                            flash(f'Successfully processed {added_count} new transactions. Skipped {duplicate_count} duplicate transactions.', 'success')
                        else:
                            app.logger.info(f"Successfully added {added_count} transactions")
                            flash(f'Successfully processed {added_count} transactions', 'success')
                    else:
                        app.logger.warning("No transactions found in file")
                        flash('No transactions found in the file', 'info')

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error processing file: {e}")
                    flash(f'Error processing file: {str(e)}', 'error')

            except Exception as e:
                app.logger.error(f"Error handling upload: {e}")
                flash(f'Error handling file: {str(e)}', 'error')
            finally:
                # Clean up the uploaded file
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        app.logger.debug(f"Cleaned up file: {filepath}")
                    except Exception as e:
                        app.logger.error(f"Error cleaning up file {filepath}: {e}")

        return redirect(url_for('transactions'))

    @app.route('/add-transaction', methods=['GET', 'POST'])
    @login_required
    def add_transaction():
        if request.method == 'POST':
            try:
                # Parse the date
                transaction_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
                description = request.form['description']
                amount = float(request.form['amount'])
                account_source = request.form['account_source']
                category_id = request.form.get('category_id')  # This will be None if no category selected

                # Check for duplicate transactions with same description, amount, and date for this user
                existing_transaction = Transaction.query.filter_by(
                    description=description,
                    amount=amount,
                    date=transaction_date,
                    user_id=current_user.id
                ).first()

                if existing_transaction:
                    flash('A transaction with the same description, amount, and date already exists.', 'warning')
                    app.logger.debug(f"Attempted to add duplicate transaction: {description}, {amount}, {transaction_date}")
                    # Don't redirect, show the form again with the error message
                    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
                    return render_template('add_transaction_manual.html',
                                         categories=categories,
                                         today=date.today(),
                                         form_data=request.form)

                # Validate category belongs to current user if provided
                if category_id:
                    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first()
                    if not category:
                        category_id = None  # Invalid category, set to None

                # Create new transaction
                new_transaction = Transaction(
                    date=transaction_date,
                    description=description,
                    amount=amount,
                    account_source=account_source,
                    category_id=category_id,
                    user_id=current_user.id
                )

                db.session.add(new_transaction)
                db.session.commit()

                flash('Transaction added successfully!', 'success')
                return redirect(url_for('transactions'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding transaction: {str(e)}', 'error')
                app.logger.error(f'Error adding transaction: {e}')

        # For GET request, show the form
        categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
        return render_template('add_transaction_manual.html',
                             categories=categories,
                             today=date.today())

    @app.route('/edit-transaction/<int:transaction_id>', methods=['GET', 'POST'])
    @login_required
    def edit_transaction(transaction_id):
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()

        if request.method == 'POST':
            try:
                transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
                transaction.description = request.form['description']
                transaction.amount = float(request.form['amount'])
                transaction.account_source = request.form['account_source']
                category_id = request.form.get('category_id')

                # Validate category belongs to current user if provided
                if category_id:
                    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first()
                    transaction.category_id = category.id if category else None
                else:
                    transaction.category_id = None

                db.session.commit()
                flash('Transaction updated successfully!', 'success')
                return redirect(url_for('transactions'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating transaction: {str(e)}', 'error')
                app.logger.error(f'Error updating transaction: {e}')

        categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
        return render_template('edit_transaction.html',
                             transaction=transaction,
                             categories=categories)

    @app.route('/delete-transaction/<int:transaction_id>', methods=['POST'])
    @login_required
    def delete_transaction(transaction_id):
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
        try:
            db.session.delete(transaction)
            db.session.commit()
            flash('Transaction deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting transaction: {str(e)}', 'error')
            app.logger.error(f'Error deleting transaction: {e}')
        return redirect(url_for('transactions'))

    @app.route('/delete-all-transactions', methods=['POST'])
    @login_required
    def delete_all_transactions():
        try:
            transaction_count = Transaction.query.filter_by(user_id=current_user.id).count()
            if transaction_count == 0:
                flash('No transactions to delete.', 'info')
                return redirect(url_for('transactions'))

            Transaction.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            flash(f'Successfully deleted all {transaction_count} transactions!', 'success')
            app.logger.info(f'Deleted all {transaction_count} transactions for user {current_user.id}')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting all transactions: {str(e)}', 'error')
            app.logger.error(f'Error deleting all transactions: {e}')
        return redirect(url_for('transactions'))

    # Keep existing category management routes
    @app.route('/manage-categories')
    @login_required
    def serve_category_manager_html():
        return render_template('category_manager.html')

    # Keep all existing category API endpoints
    @app.route('/api/categories', methods=['GET'])
    @login_required
    def get_categories():
        try:
            categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
            return jsonify([category.to_dict() for category in categories])
        except Exception as e:
            app.logger.error(f"Error getting categories: {e}")
            return jsonify({"error": "Failed to retrieve categories"}), 500

    @app.route('/api/categories', methods=['POST'])
    @login_required
    @csrf.exempt
    def add_category():
        data = request.get_json()
        if not data or not data.get('name') or not data.get('name').strip():
            return jsonify({'error': 'Category name is required and cannot be empty'}), 400

        name = data['name'].strip()
        is_fixed_cost = data.get('is_fixed_cost', False)  # Default to False if not provided

        if Category.query.filter(db.func.lower(Category.name) == db.func.lower(name), Category.user_id == current_user.id).first():
            return jsonify({'error': f'Category named "{name}" already exists (case-insensitive).'}), 409

        try:
            new_category = Category(name=name, user_id=current_user.id, is_fixed_cost=is_fixed_cost)
            db.session.add(new_category)
            db.session.commit()
            app.logger.info(f"Added category: {name} (Fixed: {is_fixed_cost})")
            return jsonify(new_category.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding category {name}: {e}")
            return jsonify({"error": f"Failed to add category {name}"}), 500

    @app.route('/api/categories/<int:category_id>', methods=['PUT'])
    @login_required
    @csrf.exempt
    def update_category(category_id):
        category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
        data = request.get_json()
        if not data or not data.get('name') or not data.get('name').strip():
            return jsonify({'error': 'New category name is required and cannot be empty'}), 400

        new_name = data['name'].strip()
        is_fixed_cost = data.get('is_fixed_cost', category.is_fixed_cost)  # Keep existing value if not provided

        existing_category = Category.query.filter(
            db.func.lower(Category.name) == db.func.lower(new_name),
            Category.user_id == current_user.id
        ).filter(Category.id != category_id).first()

        if existing_category:
            return jsonify({'error': f'Another category named "{new_name}" already exists (case-insensitive).'}), 409

        try:
            category.name = new_name
            category.is_fixed_cost = is_fixed_cost
            db.session.commit()
            app.logger.info(f"Updated category ID {category_id} to: {new_name} (Fixed: {is_fixed_cost})")
            return jsonify(category.to_dict())
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating category ID {category_id}: {e}")
            return jsonify({"error": f"Failed to update category {category.name}"}), 500

    @app.route('/api/categories/<int:category_id>', methods=['DELETE'])
    @login_required
    @csrf.exempt
    def delete_category(category_id):
        category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
        try:
            category_name = category.name
            db.session.delete(category)
            db.session.commit()
            app.logger.info(f"Deleted category: {category_name} (ID: {category_id})")
            return jsonify({'message': f'Category "{category_name}" deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error deleting category ID {category_id}: {e}")
            return jsonify({"error": f"Failed to delete category {category.name}"}), 500

    @app.route('/api/categories/<int:category_id>/rules', methods=['POST'])
    @login_required
    @csrf.exempt
    def add_rule_to_category(category_id):
        category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
        data = request.get_json()
        if not data or not data.get('keyword_pattern') or not data.get('keyword_pattern').strip():
            return jsonify({'error': 'Keyword pattern is required and cannot be empty'}), 400

        keyword = data['keyword_pattern'].strip()
        if Rule.query.filter_by(category_id=category_id, keyword_pattern=keyword).first():
            return jsonify({'error': f'Keyword "{keyword}" already exists for category "{category.name}".'}), 409

        try:
            new_rule = Rule(keyword_pattern=keyword, category_id=category.id)
            db.session.add(new_rule)
            db.session.commit()
            app.logger.info(f"Added rule '{keyword}' to category: {category.name}")
            return jsonify(category.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding rule '{keyword}' to category {category.name}: {e}")
            return jsonify({"error": f"Failed to add rule to category {category.name}"}), 500

    @app.route('/api/rules/<int:rule_id>', methods=['PUT'])
    @login_required
    @csrf.exempt
    def update_rule(rule_id):
        rule = Rule.query.get_or_404(rule_id)
        # Verify that the rule belongs to a category owned by the current user
        if rule.category.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        data = request.get_json()
        if not data or not data.get('keyword_pattern') or not data.get('keyword_pattern').strip():
            return jsonify({'error': 'New keyword pattern is required and cannot be empty'}), 400

        new_keyword = data['keyword_pattern'].strip()
        existing_rule = Rule.query.filter_by(
            category_id=rule.category_id,
            keyword_pattern=new_keyword
        ).filter(Rule.id != rule_id).first()

        if existing_rule:
            category_name = rule.category.name
            return jsonify({'error': f'Keyword "{new_keyword}" already exists for category "{category_name}".'}), 409

        try:
            original_keyword = rule.keyword_pattern
            rule.keyword_pattern = new_keyword
            db.session.commit()
            app.logger.info(f"Updated rule ID {rule_id} from '{original_keyword}' to '{new_keyword}'")
            updated_category = Category.query.get(rule.category_id)
            return jsonify(updated_category.to_dict())
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating rule ID {rule_id}: {e}")
            return jsonify({"error": "Failed to update rule"}), 500

    @app.route('/api/rules/<int:rule_id>', methods=['DELETE'])
    @login_required
    @csrf.exempt
    def delete_rule(rule_id):
        rule = Rule.query.get_or_404(rule_id)
        # Verify that the rule belongs to a category owned by the current user
        if rule.category.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        try:
            category_id = rule.category_id
            keyword_pattern = rule.keyword_pattern
            db.session.delete(rule)
            db.session.commit()
            app.logger.info(f"Deleted rule: {keyword_pattern} (ID: {rule_id}) from category ID {category_id}")
            category = Category.query.get(category_id)
            return jsonify(category.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error deleting rule ID {rule_id}: {e}")
            return jsonify({"error": "Failed to delete rule"}), 500

    @app.route('/api/available-months')
    @login_required
    def get_available_months():
        """Get all months that have transaction data"""
        from sqlalchemy import func, distinct

        # Get distinct year-month combinations from transactions for current user
        months_data = db.session.query(
            extract('year', Transaction.date).label('year'),
            extract('month', Transaction.date).label('month'),
            func.count(Transaction.id).label('transaction_count')
        ).filter(
            Transaction.user_id == current_user.id
        ).group_by(
            extract('year', Transaction.date),
            extract('month', Transaction.date)
        ).order_by(
            extract('year', Transaction.date).desc(),
            extract('month', Transaction.date).desc()
        ).all()

        available_months = []
        for year, month, count in months_data:
            available_months.append({
                'year': int(year),
                'month': int(month),
                'month_name': calendar.month_name[int(month)],
                'transaction_count': count,
                'url': url_for('home', year=int(year), month=int(month))
            })

        return jsonify(available_months)

    @app.route('/api/fixed-costs-analysis/<int:year>/<int:month>')
    @login_required
    def get_fixed_costs_analysis(year, month):
        """Get fixed vs variable costs analysis for a specific month/year"""
        from sqlalchemy import func
        from datetime import date

        try:
            # Calculate start and end dates for the specified month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)

            # Get transactions for the month with category info
            transactions_query = db.session.query(
                Transaction.amount,
                Category.is_fixed_cost,
                Category.name
            ).join(
                Category, Transaction.category_id == Category.id, isouter=True
            ).filter(
                Transaction.date >= start_date,
                Transaction.date < end_date,
                Transaction.user_id == current_user.id,
                Transaction.amount < 0  # Only expenses (negative amounts)
            )

            transactions = transactions_query.all()

            # Calculate totals
            fixed_costs_total = 0
            variable_costs_total = 0
            fixed_costs_categories = {}
            variable_costs_categories = {}

            for amount, is_fixed_cost, category_name in transactions:
                abs_amount = abs(amount)  # Convert to positive for display
                category_name = category_name or 'Uncategorized'

                if is_fixed_cost:
                    fixed_costs_total += abs_amount
                    fixed_costs_categories[category_name] = fixed_costs_categories.get(category_name, 0) + abs_amount
                else:
                    variable_costs_total += abs_amount
                    variable_costs_categories[category_name] = variable_costs_categories.get(category_name, 0) + abs_amount

            total_expenses = fixed_costs_total + variable_costs_total

            # Calculate percentages
            fixed_percentage = (fixed_costs_total / total_expenses * 100) if total_expenses > 0 else 0
            variable_percentage = (variable_costs_total / total_expenses * 100) if total_expenses > 0 else 0

            return jsonify({
                'month': month,
                'year': year,
                'month_name': calendar.month_name[month],
                'fixed_costs': {
                    'total': round(fixed_costs_total, 2),
                    'percentage': round(fixed_percentage, 1),
                    'categories': {k: round(v, 2) for k, v in fixed_costs_categories.items()}
                },
                'variable_costs': {
                    'total': round(variable_costs_total, 2),
                    'percentage': round(variable_percentage, 1),
                    'categories': {k: round(v, 2) for k, v in variable_costs_categories.items()}
                },
                'total_expenses': round(total_expenses, 2)
            })
        except Exception as e:
            app.logger.error(f"Error getting fixed costs analysis for {year}-{month}: {e}")
            return jsonify({"error": "Failed to retrieve fixed costs analysis"}), 500

    # Budget API endpoints
    @app.route('/api/budgets/<int:year>/<int:month>', methods=['GET'])
    @login_required
    def get_budgets(year, month):
        """Get all budgets for a specific month/year"""
        try:
            budgets = Budget.query.filter_by(month=month, year=year, user_id=current_user.id).all()
            return jsonify([budget.to_dict() for budget in budgets])
        except Exception as e:
            app.logger.error(f"Error getting budgets for {year}-{month}: {e}")
            return jsonify({"error": "Failed to retrieve budgets"}), 500

    @app.route('/api/budgets', methods=['POST'])
    @login_required
    @csrf.exempt
    def set_budget():
        """Set or update a budget for a category/month/year"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data is required'}), 400

        required_fields = ['category_id', 'month', 'year', 'budgeted_amount']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        category_id = data['category_id']
        month = data['month']
        year = data['year']
        budgeted_amount = float(data['budgeted_amount'])

        # Validate inputs
        if not (1 <= month <= 12):
            return jsonify({'error': 'Month must be between 1 and 12'}), 400

        if year < 2000 or year > 2100:
            return jsonify({'error': 'Year must be between 2000 and 2100'}), 400

        if budgeted_amount < 0:
            return jsonify({'error': 'Budget amount cannot be negative'}), 400

        # Check if category exists and belongs to current user
        category = Category.query.filter_by(id=category_id, user_id=current_user.id).first()
        if not category:
            return jsonify({'error': 'Category not found'}), 404

        try:
            # Check if budget already exists for this user
            existing_budget = Budget.query.filter_by(
                category_id=category_id,
                month=month,
                year=year,
                user_id=current_user.id
            ).first()

            if existing_budget:
                # Update existing budget
                existing_budget.budgeted_amount = budgeted_amount
                db.session.commit()
                app.logger.info(f"Updated budget for {category.name} {year}-{month:02d}: ${budgeted_amount}")
                return jsonify(existing_budget.to_dict())
            else:
                # Create new budget
                new_budget = Budget(
                    category_id=category_id,
                    month=month,
                    year=year,
                    budgeted_amount=budgeted_amount,
                    user_id=current_user.id
                )
                db.session.add(new_budget)
                db.session.commit()
                app.logger.info(f"Created budget for {category.name} {year}-{month:02d}: ${budgeted_amount}")
                return jsonify(new_budget.to_dict()), 201

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error setting budget: {e}")
            return jsonify({"error": "Failed to set budget"}), 500

    @app.route('/api/budgets/<int:budget_id>', methods=['DELETE'])
    @login_required
    @csrf.exempt
    def delete_budget(budget_id):
        """Delete a budget"""
        budget = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first_or_404()
        try:
            category_name = budget.category.name if budget.category else 'Unknown'
            db.session.delete(budget)
            db.session.commit()
            app.logger.info(f"Deleted budget: {category_name} {budget.year}-{budget.month:02d}")
            return jsonify({'message': f'Budget for {category_name} deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error deleting budget ID {budget_id}: {e}")
            return jsonify({"error": "Failed to delete budget"}), 500

    @app.route('/api/budgets/carry-over', methods=['POST'])
    @login_required
    @csrf.exempt
    def carry_over_budgets():
        """Carry over current month's budgets to future months"""
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta

        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data is required'}), 400

        source_month = data.get('source_month')
        source_year = data.get('source_year')
        target_months = data.get('target_months', 12)  # Default to 12 months

        if not source_month or not source_year:
            return jsonify({'error': 'source_month and source_year are required'}), 400

        # Validate inputs
        if not (1 <= source_month <= 12):
            return jsonify({'error': 'Source month must be between 1 and 12'}), 400

        if source_year < 2000 or source_year > 2100:
            return jsonify({'error': 'Source year must be between 2000 and 2100'}), 400

        if not (1 <= target_months <= 60):  # Max 5 years
            return jsonify({'error': 'Target months must be between 1 and 60'}), 400

        try:
            # Get all budgets for the source month/year for current user
            source_budgets = Budget.query.filter_by(
                month=source_month,
                year=source_year,
                user_id=current_user.id
            ).all()

            if not source_budgets:
                return jsonify({'error': f'No budgets found for {source_year}-{source_month:02d}'}), 404

            budgets_created = 0
            budgets_updated = 0

            # Start from the next month after the source month
            current_date = datetime(source_year, source_month, 1) + relativedelta(months=1)

            for month_offset in range(target_months):
                target_month = current_date.month
                target_year = current_date.year

                for source_budget in source_budgets:
                    # Check if budget already exists for this category/month/year
                    existing_budget = Budget.query.filter_by(
                        category_id=source_budget.category_id,
                        month=target_month,
                        year=target_year,
                        user_id=current_user.id
                    ).first()

                    if existing_budget:
                        # Update existing budget
                        existing_budget.budgeted_amount = source_budget.budgeted_amount
                        budgets_updated += 1
                    else:
                        # Create new budget
                        new_budget = Budget(
                            category_id=source_budget.category_id,
                            month=target_month,
                            year=target_year,
                            budgeted_amount=source_budget.budgeted_amount,
                            user_id=current_user.id
                        )
                        db.session.add(new_budget)
                        budgets_created += 1

                # Move to next month
                current_date += relativedelta(months=1)

            db.session.commit()

            app.logger.info(f"Carried over budgets from {source_year}-{source_month:02d} for {target_months} months: {budgets_created} created, {budgets_updated} updated")

            return jsonify({
                'message': f'Successfully carried over budgets for {target_months} months',
                'budgets_created': budgets_created,
                'budgets_updated': budgets_updated,
                'source_month': source_month,
                'source_year': source_year,
                'target_months': target_months
            }), 200

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error carrying over budgets: {e}")
            return jsonify({"error": "Failed to carry over budgets"}), 500

    @app.route('/api/add-default-categories', methods=['POST'])
    @login_required
    @csrf.exempt
    def add_default_categories():
        """Add default categories for the current user"""
        try:
            # Check if user already has categories
            existing_categories = Category.query.filter_by(user_id=current_user.id).count()
            if existing_categories > 0:
                return jsonify({'error': 'User already has categories'}), 400

            # Create default categories for this user
            create_default_categories_for_user(current_user.id)

            app.logger.info(f"Added default categories for user: {current_user.email}")
            return jsonify({'message': 'Default categories added successfully'}), 200

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding default categories for user {current_user.id}: {e}")
            return jsonify({'error': 'Failed to add default categories'}), 500

    # --- CLI commands for DB management ---
    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        app.logger.info("Initialized the database and created/updated tables based on models.")
        app.logger.info("To manage database migrations for production, use: flask db init, flask db migrate, flask db upgrade")
        app.logger.info("Default categories will be created automatically when users register.")

    @app.cli.command("create-default-categories")
    def create_default_categories_command():
        """Create default categories for existing users or a specific user."""
        import click

        users = User.query.all()
        if not users:
            app.logger.info("No users found. Categories will be created when users register.")
            return

        default_categories_rules = {
            "Groceries": ["superstore", "save on foods", "wal-mart groceries"],
            "Dining Out/Cafe": ["mcdonald's", "tim hortons", "starbucks", "subway", "pizza"],
            "Food Delivery": ["uber eats", "doordash", "skipTheDishes"],
            "Bills/Utilities": ["fido mobile", "fortisbc energy", "hydro"],
            "Subscriptions/Entertainment": ["netflix.com", "spotify", "disney plus"],
            "Subscriptions/Services": ["apple.com/bill", "google cloud"],
            "Shopping/Online": ["amazon.ca", "temu.com", "ebay"],
            "Shopping/General Merchandise": ["wal-mart", "dollarama", "winners"],
            "Healthcare": ["pharmacy", "clinic", "dental"],
            "Insurance": ["icbc", "square one insurance", "life insurance"],
            "Car": ["gas station", "esso", "shell", "petro-canada", "mechanic", "car wash"],
            "Investments": ["questrade", "wealthsimple"],
            "Transfers": ["e-transfer", "send money"],
            "Credit Card Payment": ["payment - thank you", "cibc visa payment", "td mc payment"],
            "Housing": ["rent", "mortgage", "strata fee"],
            "Childcare/Education": ["daycare", "school fees"],
            "Therapy": [],
            "Travel": ["expedia", "booking.com", "airbnb", "flights"],
            "Miscellaneous": ["misc", "other"]
        }

        for user in users:
            if Category.query.filter_by(user_id=user.id).first():
                app.logger.info(f"User {user.email} already has categories, skipping...")
                continue

            app.logger.info(f"Creating default categories for user: {user.email}")
            for cat_name, rules_list in default_categories_rules.items():
                category = Category(name=cat_name, user_id=user.id)
                db.session.add(category)
                db.session.flush()
                for rule_kw in rules_list:
                    rule = Rule(keyword_pattern=rule_kw, category_id=category.id)
                    db.session.add(rule)
            db.session.commit()
            app.logger.info(f"Successfully created default categories for user: {user.email}")



    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        db.create_all()
    app.run(debug=True, port=5001)
else:
    # For production (Gunicorn will import this)
    app = create_app()
    with app.app_context():
        # Ensure upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])