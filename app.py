from flask import Flask, render_template, request, redirect, url_for, flash
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename # For securely saving filenames
from datetime import datetime, date, timedelta # Ensure timedelta is imported
from collections import defaultdict # For calculating category sums
import json # For passing data to JavaScript
import calendar # For month names
from sqlalchemy import extract # For filtering by month/year

from extensions import db
from models import Transaction
from parser import process_uploaded_file # Import the parser function
from categorizer import assign_category, get_defined_categories # Add get_defined_categories

load_dotenv() # Load environment variables from .env


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_default_secret_key') # Add a secret key
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///budget.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'uploads'

    db.init_app(app) # Initialize db with the app

    @app.route('/')
    def index():
        try:
            current_year = datetime.now().year
            current_month = datetime.now().month

            year = request.args.get('year', current_year, type=int)
            month = request.args.get('month', current_month, type=int)

            # Ensure month and year are within reasonable bounds (e.g., month 1-12)
            if not (1 <= month <= 12):
                month = current_month # Default to current month if invalid
            # Add year validation if necessary, e.g., if year < 2000 or year > current_year + 5: year = current_year

            # Fetch transactions for the selected month and year
            transactions_for_month = db.session.query(Transaction).filter(
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).order_by(Transaction.date.desc()).all()

            # Calculate totals for the selected month
            total_spending_for_month = 0
            total_income_for_month = 0
            spending_by_category = defaultdict(float)
            for t in transactions_for_month:
                if t.amount < 0: # Expenses
                    total_spending_for_month += abs(t.amount)
                    category = t.category if t.category else "Uncategorized"
                    spending_by_category[category] += abs(t.amount)
                elif t.amount > 0: # Income
                    total_income_for_month += t.amount

            net_balance_for_month = total_income_for_month - total_spending_for_month

            chart_labels = list(spending_by_category.keys())
            chart_data = list(spending_by_category.values())

            # Get top 7 spending categories
            sorted_spending = sorted(spending_by_category.items(), key=lambda item: item[1], reverse=True)
            top_7_spending_categories = sorted_spending[:7]

            # Get month name for display
            month_name = calendar.month_name[month]

            # Basic next/prev month logic
            prev_month_date = date(year, month, 1) - timedelta(days=1)
            next_month_date = date(year, month, 28) + timedelta(days=4) # Go to approx end of month then add 4 days to ensure next month
            next_month_date = next_month_date.replace(day=1) # First day of next month

            prev_month_params = {'year': prev_month_date.year, 'month': prev_month_date.month}
            next_month_params = {'year': next_month_date.year, 'month': next_month_date.month}

            return render_template(
                'index.html',
                transactions=transactions_for_month,
                chart_labels=json.dumps(chart_labels),
                chart_data=json.dumps(chart_data),
                selected_year=year,
                selected_month=month,
                selected_month_name=month_name,
                total_spending_for_month=total_spending_for_month,
                total_income_for_month=total_income_for_month,
                net_balance_for_month=net_balance_for_month,
                top_7_spending_categories=top_7_spending_categories,
                prev_month_params=prev_month_params,
                next_month_params=next_month_params
            )
        except Exception as e:
            print(f"Error in index route: {e}")
            flash("An error occurred while loading the dashboard. Please try again.", "error")
            # Render with minimal context or redirect to a safe page
            return render_template('index.html', transactions=[], chart_labels='[]', chart_data='[]',
                                   selected_year=datetime.now().year, selected_month=datetime.now().month,
                                   selected_month_name=calendar.month_name[datetime.now().month],
                                   total_spending_for_month=0, total_income_for_month=0, net_balance_for_month=0,
                                   top_7_spending_categories=[],
                                   prev_month_params={}, next_month_params={})

    @app.route('/upload', methods=['POST'])
    def upload_files():
        if 'files[]' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        files = request.files.getlist('files[]')

        if not files or files[0].filename == '':
            flash('No selected files', 'error')
            return redirect(request.url)

        newly_added_count = 0
        skipped_duplicates_count = 0
        error_files = []
        processed_files_count = 0

        for file_item in files:
            if file_item and file_item.filename:
                filename = secure_filename(file_item.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file_item.save(file_path)
                processed_files_count +=1

                try:
                    potential_transactions = process_uploaded_file(file_path, filename)
                    transactions_to_add = []

                    if potential_transactions:
                        for pt in potential_transactions:
                            # Check for duplicates before adding
                            exists = db.session.query(Transaction).filter_by(
                                date=pt.date,
                                description=pt.description,
                                amount=pt.amount,
                                account_source=pt.account_source
                            ).first()

                            if not exists:
                                transactions_to_add.append(pt)
                            else:
                                skipped_duplicates_count += 1

                        if transactions_to_add:
                            db.session.add_all(transactions_to_add)
                            db.session.commit()
                            newly_added_count += len(transactions_to_add)
                            # Flash per file success is now handled in the summary below
                        # else: # All were duplicates or no valid transactions
                            # No specific flash here, summary will cover it
                    #else: # No transactions parsed from file
                        # No specific flash here, summary will cover it

                except Exception as e:
                    db.session.rollback()
                    print(f"Error processing file {filename}: {e}")
                    flash(f'Error processing file {filename}. Check logs.', 'error')
                    error_files.append(filename)
            else:
                flash('Encountered an issue with one of the uploaded files (e.g., no filename).', 'warning')

        # Consolidated Flash Messages
        if newly_added_count > 0:
            flash(f'Successfully imported {newly_added_count} new transactions.', 'success')
        if skipped_duplicates_count > 0:
            flash(f'Skipped {skipped_duplicates_count} duplicate transactions.', 'info')
        if error_files:
            flash(f'Errors occurred with files: {", ".join(error_files)}. Check logs.', 'error')
        if processed_files_count > 0 and newly_added_count == 0 and skipped_duplicates_count == 0 and not error_files:
             flash('Files processed, but no new transactions were imported (they may all be duplicates or files were empty/unparseable).', 'info')
        elif processed_files_count == 0 and not error_files:
            # This case should ideally be caught by earlier checks, but as a fallback.
            if not request.files.getlist('files[]')[0].filename: # If initial check for no selected files passed due to empty filename string
                 pass # Already flashed "No selected files"
            else:
                flash('No files were processed.', 'info')

        # The redirect for upload_files should be after all flash messages:
        current_redirect_year = datetime.now().year
        current_redirect_month = datetime.now().month
        # If new transactions were added, try to redirect to the month of the first new transaction if possible,
        # otherwise default to current month. This is a bit more complex to get right here as transactions_to_add is in a loop.
        # For simplicity, defaulting to current month after uploads.
        return redirect(url_for('index', year=current_redirect_year, month=current_redirect_month))

    @app.route('/add_manual', methods=['GET', 'POST'])
    def add_transaction_manual():
        if request.method == 'POST':
            try:
                date_str = request.form['date']
                description = request.form['description']
                amount_str = request.form['amount']
                account_source = request.form['account_source']
                category_manual = request.form.get('category') # User-provided category

                if not date_str or not description or not amount_str or not account_source:
                    flash('Date, Description, Amount, and Account Source are required.', 'error')
                    # Pass back form data to avoid user re-entering everything
                    return render_template('add_transaction_manual.html', form_data=request.form, categories=get_defined_categories())

                transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                amount = float(amount_str)

                final_category = category_manual
                if not final_category and description: # If user didn't provide category, try to auto-assign
                    final_category = assign_category(description)

                new_transaction = Transaction(
                    date=transaction_date,
                    description=description,
                    amount=amount,
                    account_source=account_source,
                    category=final_category if final_category else None
                )
                db.session.add(new_transaction)
                db.session.commit()
                flash('Manual transaction added successfully!', 'success')
                return redirect(url_for('index', year=transaction_date.year, month=transaction_date.month))
            except ValueError:
                flash('Invalid data submitted. Amount must be a number and Date must be valid.', 'error')
                return render_template('add_transaction_manual.html', form_data=request.form, categories=get_defined_categories())
            except Exception as e:
                flash(f'An error occurred: {str(e)}', 'error')
                db.session.rollback()
                return render_template('add_transaction_manual.html', form_data=request.form, categories=get_defined_categories())

        return render_template('add_transaction_manual.html', form_data={}, categories=get_defined_categories())

    @app.route('/edit/<int:transaction_id>', methods=['GET', 'POST'])
    def edit_transaction(transaction_id):
        transaction = db.session.get(Transaction, transaction_id)
        defined_categories = get_defined_categories()
        if not transaction:
            flash('Transaction not found.', 'error')
            return redirect(url_for('index'))

        if request.method == 'POST':
            try:
                transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
                transaction.description = request.form['description']
                transaction.amount = float(request.form['amount'])
                transaction.account_source = request.form['account_source']
                new_category = request.form.get('category')

                if not new_category or new_category == "__None__": # Check for special value for None
                    transaction.category = assign_category(transaction.description)
                else:
                    transaction.category = new_category

                db.session.commit()
                flash('Transaction updated successfully!', 'success')
                return redirect(url_for('index', year=transaction.date.year, month=transaction.date.month))
            except ValueError:
                flash('Invalid data. Please check amount and date.', 'error')
                return render_template('edit_transaction.html', transaction=transaction, form_data=request.form, categories=defined_categories)
            except Exception as e:
                flash(f'Error updating transaction: {str(e)}', 'error')
                db.session.rollback()
                return render_template('edit_transaction.html', transaction=transaction, form_data=request.form, categories=defined_categories)

        return render_template('edit_transaction.html', transaction=transaction, form_data={}, categories=defined_categories)

    @app.route('/delete/<int:transaction_id>', methods=['POST'])
    def delete_transaction(transaction_id):
        transaction = db.session.get(Transaction, transaction_id)
        if transaction:
            try:
                # Store date before deleting to redirect to the correct month
                redirect_year = transaction.date.year
                redirect_month = transaction.date.month
                db.session.delete(transaction)
                db.session.commit()
                flash('Transaction deleted successfully!', 'success')
                return redirect(url_for('index', year=redirect_year, month=redirect_month))
            except Exception as e:
                db.session.rollback()
                flash(f'Error deleting transaction: {str(e)}', 'error')
        else:
            flash('Transaction not found.', 'error')
        return redirect(url_for('index'))

    @app.route('/delete_all', methods=['POST'])
    def delete_all_transactions():
        try:
            num_rows_deleted = db.session.query(Transaction).delete()
            db.session.commit()
            if num_rows_deleted > 0:
                flash(f'Successfully deleted all {num_rows_deleted} transactions!', 'success')
            else:
                flash('No transactions to delete.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting all transactions: {str(e)}', 'error')
        # For delete_all and upload, redirecting to current month is a sensible default
        # as these actions aren't tied to a specific transaction's month.
        return redirect(url_for('index', year=datetime.now().year, month=datetime.now().month))

    with app.app_context():
        # Ensure the upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        db.create_all() # Create database tables if they don't exist

    return app

app = create_app() # Create the app instance for flask run and other tools

if __name__ == '__main__':
    app.run(debug=True)