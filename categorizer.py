import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Assuming models.py and extensions.py are in the same directory or accessible in PYTHONPATH
# and app.py initializes the db with the app context.
from models import Category, Rule # Import your SQLAlchemy models
from extensions import db # Import the db instance

# To allow this module to be used standalone or within a Flask app context,
# we need a way to access the database.
# If running within Flask, app context provides this.
# If standalone, we might need to create an engine and session.

# Option 1: For use within a Flask App (preferred if this is part of the Flask app)
# Ensure an app context is available when these functions are called.
# from flask import current_app

# Option 2: For standalone use or testing, you might need to configure a session.
# This requires knowing the database URI. It's better if the app manages this.
# For now, let's assume these functions will be called from within an app context
# or the context will be provided/pushed by the caller.

@contextmanager
def get_db_session():
    """Provides a DB session. Uses existing session from app context."""
    from flask import current_app, has_app_context
    if has_app_context():
        yield db.session
    else:
        print("Warning: No Flask app context available. Using direct database connection.")
        try:
            from app import create_app
            temp_app = create_app()
            with temp_app.app_context():
                yield db.session
        except Exception as e:
            print(f"Error creating database session: {e}")
            yield None

def assign_category(description):
    """Assigns a category to a transaction based on its description using DB rules."""
    if not description:
        return None

    desc_lower = description.lower()

    with get_db_session() as session:
        if not session:
            print("Error: No DB session available in assign_category.")
            return None

        try:
            # Get all rules ordered by length (longer rules first for more specificity)
            rules = session.query(Rule).join(Category).order_by(db.func.length(Rule.keyword_pattern).desc()).all()

            for rule in rules:
                try:
                    # Convert wildcards to regex pattern
                    if '*' in rule.keyword_pattern:
                        regex_parts = [re.escape(part) for part in rule.keyword_pattern.split('*')]
                        pattern_to_search = '.*'.join(regex_parts)
                    else:
                        pattern_to_search = re.escape(rule.keyword_pattern)

                    # Search for pattern in description
                    if re.search(pattern_to_search, desc_lower, re.IGNORECASE):
                        return rule.category.name

                except re.error as e:
                    print(f"Regex error for rule '{rule.keyword_pattern}' (ID: {rule.id}): {e}")
                    continue

        except Exception as e:
            print(f"Error assigning category: {e}")
            return None

    return None

def get_defined_categories():
    """Returns a sorted list of unique category names from the database."""
    with get_db_session() as session:
        if not session:
            print("Error: No DB session available in get_defined_categories.")
            return []

        try:
            categories = session.query(Category.name).order_by(Category.name).all()
            return [category[0] for category in categories]
        except Exception as e:
            print(f"Error getting categories: {e}")
            return []

# --- Old hardcoded rules - keep for reference or removal ---
# CATEGORIZATION_RULES = {
#     # ... your old rules ...
# }

# Example of how to test this standalone (requires Flask app structure and DB URI)
if __name__ == '__main__':
    print("Testing categorizer with DB...")

    # This standalone test requires the Flask app to be initializable
    # and the database (e.g., categories_rules.db) to be created and possibly seeded.
    # Run `flask init-db` from your app directory first.

    print("Fetching all defined categories from DB:")
    defined_cats = get_defined_categories()
    if defined_cats and "Error: DB Unavailable" not in defined_cats:
        print(f"> {defined_cats}")
    else:
        print("> Could not fetch categories from DB for standalone test.")

    print("\nTesting assignments:")
    test_descriptions = [
        "Uber Eats Toronto",
        "TIM HORTONS #1234",
        "My monthly NETFLIX.COM bill",
        "AMAZON.CA PURCHASE",
        "Gas station fill-up",
        "FortisBC Energy Inc.",
        "ICBC Insurance renewal",
        "Save on foods grocery run",
        "Non existent rule"
    ]
    for desc in test_descriptions:
        category = assign_category(desc)
        print(f"> '{desc}' -> '{category or "Uncategorized"}'")

    print("\nTest with a wildcard rule (if seeded): e.g. 'hp *instant ink'")
    hp_test = assign_category("Payment to HP for instant ink service")
    print(f"> 'Payment to HP for instant ink service' -> '{hp_test or "Uncategorized"}'")

    print("\nIf your database is empty, run 'flask init-db' in your app directory.")