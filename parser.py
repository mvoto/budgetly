import csv
from datetime import datetime
# from app import db # This line causes circular import and is not needed here
from models import Transaction
from categorizer import assign_category # Import the new categorizer function

# Helper to convert amount strings from CSVs
def _parse_amount(debit_str, credit_str=None):
    debit = 0.0
    if debit_str:
        try:
            debit = float(debit_str.strip().replace('-', '').replace(',', '')) # Handle potential commas or negative signs if present
        except ValueError:
            pass # Or log error

    credit = 0.0
    if credit_str:
        try:
            credit = float(credit_str.strip().replace(',', ''))
        except ValueError:
            pass # Or log error

    if debit > 0:
        return -debit # Expenses are negative
    elif credit > 0:
        return credit
    return 0.0

def _parse_td_common(file_path, account_source):
    transactions = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f: # utf-8-sig to handle potential BOM
            reader = csv.reader(f)
            for row in reader:
                if not row or len(row) < 3: # Basic check for valid row
                    continue
                try:
                    date_str = row[0].strip()
                    description = row[1].strip()
                    # Debit in col 2 (index), Credit in col 4 (index) for some TD files
                    # Or Debit in col 2, Credit in col 3 for others
                    debit_val = row[2].strip() if len(row) > 2 else None
                    credit_val = row[4].strip() if len(row) > 4 else (row[3].strip() if len(row) > 3 and debit_val and not row[3].strip() else None)

                    # Refined logic for TD files where debit is one col, credit is another, and one is blank
                    # td-cb-may-accountactivity.csv: Date,Desc,Debit,,Credit,Balance (0,1,2,3,4,5)
                    # td-in-may-accountactivity.csv: Date,Desc,Debit,,Credit,Balance (0,1,2,3,4,5)
                    if len(row) >= 5 and row[3] == '' : # Debit in col 2, Credit in col 4
                         amount = _parse_amount(row[2], row[4])
                    elif len(row) >= 4: # Debit in col 2, Credit in col 3
                         amount = _parse_amount(row[2], row[3])
                    else:
                        continue # Not enough columns

                    if amount == 0.0 and not description.lower().startswith("payment - thank you"): # Avoid zero amount unless it is a known non-monetary like a payment confirmation
                         # Check if it's a payment thank you, those can have 0 if we only look at one side
                        is_payment = description.lower().startswith("payment - thank you")
                        if not is_payment and (not row[2] or not row[4] if len(row) >=5 else not row[3]): # If it's not a payment and one of the amount columns is empty, it might be bad data
                             # print(f"Skipping zero amount transaction: {row}") # Optional: log
                             pass # Continue if amount is zero unless it's a clear payment line

                    if date_str and description and amount != 0.0:
                        transaction_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                        category = assign_category(description) # Assign category
                        transactions.append({
                            'date': transaction_date,
                            'description': description,
                            'amount': amount,
                            'account_source': account_source,
                            'category': category # Add category to dict
                        })
                except (IndexError, ValueError) as e:
                    print(f"Skipping row in TD Common due to error: {row} - {e}")
                    continue
    except Exception as e:
        print(f"Error reading TD Common file {file_path}: {e}")
    return transactions

def _parse_td_chequing_new(file_path, account_source):
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
                        category = assign_category(description) # Assign category
                        transactions.append({
                            'date': transaction_date,
                            'description': description,
                            'amount': amount,
                            'account_source': account_source,
                            'category': category # Add category to dict
                        })
                except (IndexError, ValueError) as e:
                    print(f"Skipping row in TD Chequing due to error: {row} - {e}")
                    continue
    except Exception as e:
        print(f"Error reading TD Chequing file {file_path}: {e}")
    return transactions

def _parse_amex(file_path, account_source):
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
                        category = assign_category(description) # Assign category
                        transactions.append({
                            'date': transaction_date,
                            'description': description,
                            'amount': amount,
                            'account_source': account_source,
                            'category': category # Add category to dict
                        })
                except (IndexError, ValueError) as e:
                    print(f"Skipping row in Amex due to error: {row} - {e}")
                    continue
    except Exception as e:
        print(f"Error reading Amex file {file_path}: {e}")
    return transactions

def process_uploaded_file(file_path, original_filename):
    original_filename_lower = original_filename.lower()
    parsed_txns = []

    if 'amex' in original_filename_lower:
        print(f"Processing Amex file: {original_filename}")
        parsed_txns = _parse_amex(file_path, 'American Express')
    elif 'td' in original_filename_lower:
        # Try to differentiate TD file types
        # This is heuristic, might need refinement based on more examples or stricter naming
        if 'cb' in original_filename_lower or 'in' in original_filename_lower: # td-cb-may-accountactivity.csv or td-in-may-accountactivity.csv
            account_name = 'TD Credit Card' if 'cb' in original_filename_lower else 'TD Account IN'
            print(f"Processing TD Common file: {original_filename} as {account_name}")
            parsed_txns = _parse_td_common(file_path, account_name)
        else: # td-may-accountactivity.csv (assumed Chequing style)
            print(f"Processing TD Chequing style file: {original_filename}")
            parsed_txns = _parse_td_chequing_new(file_path, 'TD Chequing')
    else:
        print(f"Unknown file type for: {original_filename}")
        # Optionally, try a generic parser or mark as unparseable

    # Convert parsed data to Transaction objects
    transaction_objects = []
    if parsed_txns:
        for txn_data in parsed_txns:
            transaction_objects.append(Transaction(**txn_data))

    return transaction_objects