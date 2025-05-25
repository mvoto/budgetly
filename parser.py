import csv
from datetime import datetime
import logging
# from app import db # This line causes circular import and is not needed here
from models import Transaction, Category
from categorizer import assign_category # Import the new categorizer function

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Helper to convert amount strings from CSVs
def _parse_amount(debit_str, credit_str=None):
    debit = 0.0
    if debit_str:
        try:
            debit = float(debit_str.strip().replace('-', '').replace(',', '')) # Handle potential commas or negative signs if present
        except ValueError as e:
            logger.debug(f"Error parsing debit amount '{debit_str}': {e}")
            pass # Or log error

    credit = 0.0
    if credit_str:
        try:
            credit = float(credit_str.strip().replace(',', ''))
        except ValueError as e:
            logger.debug(f"Error parsing credit amount '{credit_str}': {e}")
            pass # Or log error

    if debit > 0:
        return -debit # Expenses are negative
    elif credit > 0:
        return credit
    return 0.0

def _parse_td_common(file_path, account_source, user_id=None):
    transactions = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f: # utf-8-sig to handle potential BOM
            reader = csv.reader(f)
            row_count = 0
            for row in reader:
                row_count += 1
                if not row or len(row) < 3: # Basic check for valid row
                    logger.debug(f"Skipping invalid row {row_count}: {row}")
                    continue
                try:
                    date_str = row[0].strip()
                    description = row[1].strip()
                    # Debit in col 2 (index), Credit in col 4 (index) for some TD files
                    # Or Debit in col 2, Credit in col 3 for others
                    debit_val = row[2].strip() if len(row) > 2 else None
                    credit_val = row[4].strip() if len(row) > 4 else (row[3].strip() if len(row) > 3 and debit_val and not row[3].strip() else None)

                    logger.debug(f"Processing row {row_count}:")
                    logger.debug(f"  Date: {date_str}")
                    logger.debug(f"  Description: {description}")
                    logger.debug(f"  Debit: {debit_val}")
                    logger.debug(f"  Credit: {credit_val}")

                    # Refined logic for TD files where debit is one col, credit is another, and one is blank
                    # td-cb-may-accountactivity.csv: Date,Desc,Debit,,Credit,Balance (0,1,2,3,4,5)
                    # td-in-may-accountactivity.csv: Date,Desc,Debit,,Credit,Balance (0,1,2,3,4,5)
                    if len(row) >= 5 and row[3] == '' : # Debit in col 2, Credit in col 4
                         amount = _parse_amount(row[2], row[4])
                    elif len(row) >= 4: # Debit in col 2, Credit in col 3
                         amount = _parse_amount(row[2], row[3])
                    else:
                        logger.debug(f"  Skipping: Not enough columns")
                        continue # Not enough columns

                    logger.debug(f"  Calculated amount: {amount}")

                    if amount == 0.0 and not description.lower().startswith("payment - thank you"): # Avoid zero amount unless it is a known non-monetary like a payment confirmation
                         # Check if it's a payment thank you, those can have 0 if we only look at one side
                        is_payment = description.lower().startswith("payment - thank you")
                        if not is_payment and (not row[2] or not row[4] if len(row) >=5 else not row[3]): # If it's not a payment and one of the amount columns is empty, it might be bad data
                             logger.debug(f"  Skipping: Zero amount non-payment transaction")
                             pass # Continue if amount is zero unless it's a clear payment line

                    if date_str and description and amount != 0.0:
                        try:
                            transaction_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                            category_name = assign_category(description, user_id)
                            logger.debug(f"  Assigned category: {category_name}")

                            transactions.append({
                                'date': transaction_date,
                                'description': description,
                                'amount': amount,
                                'account_source': account_source,
                                'category_name': category_name
                            })
                            logger.debug(f"  Transaction added successfully")
                        except ValueError as e:
                            logger.error(f"  Error parsing date '{date_str}': {e}")
                            continue
                except (IndexError, ValueError) as e:
                    logger.error(f"Error processing row {row_count} {row}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error reading TD Common file {file_path}: {e}")

    logger.info(f"Parsed {len(transactions)} transactions from TD Common file")
    return transactions

def _parse_td_chequing_new(file_path, account_source, user_id=None):
    transactions = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or len(row) < 3:
                    continue
                try:
                    date_str = row[0].strip()
                    description = row[1].strip()
                    debit_val = row[2].strip()
                    credit_val = row[3].strip() if len(row) > 3 else None

                    amount = _parse_amount(debit_val, credit_val)

                    if date_str and description and amount != 0.0:
                        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        category_name = assign_category(description, user_id)
                        transactions.append({
                            'date': transaction_date,
                            'description': description,
                            'amount': amount,
                            'account_source': account_source,
                            'category_name': category_name
                        })
                except (IndexError, ValueError) as e:
                    print(f"Skipping row in TD Chequing due to error: {row} - {e}")
                    continue
    except Exception as e:
        print(f"Error reading TD Chequing file {file_path}: {e}")
    return transactions

def _parse_amex(file_path, account_source, user_id=None):
    transactions = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            try:
                first_line = next(reader)
                if not (len(first_line) > 0 and first_line[0].strip().lower() == 'table 1'):
                    # If first line is not 'Table 1', reset file pointer or re-evaluate if it's a header
                    f.seek(0) # Reset to beginning if first line wasn't 'Table 1'
            except StopIteration:
                return [] # Empty file

            try:
                 header = next(reader) # Read the actual header row
            except StopIteration:
                return [] # File only had 'Table 1' or was empty after that

            # Find column indices dynamically from header
            try:
                date_col = header.index('Date')
                desc_col = header.index('Description')
                amount_col = header.index('Amount')
            except ValueError:
                print(f"Amex file {file_path} has missing expected columns in header: {header}")
                return []

            for row in reader:
                if not row or len(row) <= max(date_col, desc_col, amount_col):
                    continue
                try:
                    date_str = row[date_col].strip()
                    description = row[desc_col].strip()
                    amount_str = row[amount_col].strip().replace('$', '').replace(',', '')

                    # Amex amounts are charges, so they are expenses (negative for us)
                    amount = -float(amount_str) if amount_str else 0.0

                    if date_str and description and amount != 0.0:
                        # Date format example: 17 May 2025
                        transaction_date = datetime.strptime(date_str, '%d %b %Y').date()
                        category_name = assign_category(description, user_id)
                        transactions.append({
                            'date': transaction_date,
                            'description': description,
                            'amount': amount,
                            'account_source': account_source,
                            'category_name': category_name
                        })
                except (IndexError, ValueError) as e:
                    print(f"Skipping row in Amex due to error: {row} - {e}")
                    continue
    except Exception as e:
        print(f"Error reading Amex file {file_path}: {e}")
    return transactions

def _parse_td_generic(file_path, account_source, user_id=None):
    """
    Generic TD parser that handles both date formats:
    - YYYY-MM-DD (like accountactivity.csv)
    - MM/DD/YYYY (like older TD exports)
    Format: Date, Description, Debit, Credit, Balance
    """
    transactions = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            row_count = 0
            for row in reader:
                row_count += 1
                if not row or len(row) < 3:
                    logger.debug(f"Skipping invalid row {row_count}: {row}")
                    continue
                try:
                    date_str = row[0].strip().strip('"')  # Remove quotes
                    description = row[1].strip().strip('"')  # Remove quotes
                    debit_val = row[2].strip().strip('"') if len(row) > 2 else None
                    credit_val = row[3].strip().strip('"') if len(row) > 3 else None
                    # Column 4 is balance, not credit - ignore it

                    logger.debug(f"Processing row {row_count}:")
                    logger.debug(f"  Date: {date_str}")
                    logger.debug(f"  Description: {description}")
                    logger.debug(f"  Debit: {debit_val}")
                    logger.debug(f"  Credit: {credit_val}")

                    # Calculate amount - debit and credit are in separate columns
                    amount = _parse_amount(debit_val, credit_val)

                    logger.debug(f"  Calculated amount: {amount}")

                    if date_str and description and amount != 0.0:
                        # Try different date formats
                        transaction_date = None
                        date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']

                        for date_format in date_formats:
                            try:
                                transaction_date = datetime.strptime(date_str, date_format).date()
                                logger.debug(f"  Successfully parsed date with format: {date_format}")
                                break
                            except ValueError:
                                continue

                        if transaction_date is None:
                            logger.error(f"  Could not parse date '{date_str}' with any known format")
                            continue

                        category_name = assign_category(description, user_id)
                        logger.debug(f"  Assigned category: {category_name}")

                        transactions.append({
                            'date': transaction_date,
                            'description': description,
                            'amount': amount,
                            'account_source': account_source,
                            'category_name': category_name
                        })
                        logger.debug(f"  Transaction added successfully")

                except (IndexError, ValueError) as e:
                    logger.error(f"Error processing row {row_count} {row}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error reading TD Generic file {file_path}: {e}")

    logger.info(f"Parsed {len(transactions)} transactions from TD Generic file")
    return transactions

def process_uploaded_file(file_path, original_filename, user_id=None):
    logger.info(f"Processing file: {original_filename}")
    original_filename_lower = original_filename.lower()
    parsed_txns = []

    if 'amex' in original_filename_lower:
        logger.info(f"Processing as Amex file")
        parsed_txns = _parse_amex(file_path, 'American Express', user_id)
    elif 'td' in original_filename_lower:
        # Try to differentiate TD file types
        # Most TD files use the Common format with MM/DD/YYYY dates
        # Only use the Chequing format if specifically indicated
        if 'chequing' in original_filename_lower or 'chq' in original_filename_lower:
            logger.info(f"Processing as TD Chequing file")
            parsed_txns = _parse_td_chequing_new(file_path, 'TD Chequing', user_id)
        else:
            # Default to TD Common parser for most TD files
            if 'cb' in original_filename_lower:
                account_name = 'TD Credit Card'
            elif 'in' in original_filename_lower:
                account_name = 'TD Account IN'
            else:
                account_name = 'TD Account'  # Generic TD account
            logger.info(f"Processing as TD Common file: {account_name}")
            parsed_txns = _parse_td_common(file_path, account_name, user_id)
    elif ('accountactivity' in original_filename_lower or
          'account_activity' in original_filename_lower or
          'statement' in original_filename_lower or
          'export' in original_filename_lower):
        # Generic TD/bank export files
        logger.info(f"Processing as generic TD/bank export file")
        parsed_txns = _parse_td_generic(file_path, 'TD Account', user_id)
    else:
        # Try the generic TD parser as a fallback for unknown CSV files
        logger.info(f"Unknown file type '{original_filename}', trying generic TD parser as fallback")
        parsed_txns = _parse_td_generic(file_path, 'Bank Account', user_id)

    logger.info(f"Parsed {len(parsed_txns)} transactions")

    # Convert parsed data to Transaction objects
    transaction_objects = []
    if parsed_txns:
        from extensions import db
        for txn_data in parsed_txns:
            try:
                # Get the category_id from the category_name for this specific user
                category_name = txn_data.pop('category_name', None)
                category_id = None
                if category_name and user_id:
                    category = db.session.query(Category).filter(
                        Category.name == category_name,
                        Category.user_id == user_id
                    ).first()
                    if category:
                        category_id = category.id
                        logger.debug(f"Found category_id {category_id} for category '{category_name}'")
                    else:
                        logger.warning(f"No category found for name '{category_name}' for user {user_id}")

                # Create the transaction with the category_id
                transaction = Transaction(
                    date=txn_data['date'],
                    description=txn_data['description'],
                    amount=txn_data['amount'],
                    account_source=txn_data['account_source'],
                    category_id=category_id
                )
                transaction_objects.append(transaction)
                logger.debug(f"Created transaction object: {transaction.description}, {transaction.amount}, {transaction.category_id}")
            except Exception as e:
                logger.error(f"Error creating transaction object: {e}")
                continue

    logger.info(f"Created {len(transaction_objects)} transaction objects")
    return transaction_objects