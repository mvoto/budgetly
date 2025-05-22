import re

# Define categorization rules
# Order can matter if a description could match multiple keywords.
# More specific rules should generally come before more generic ones.
CATEGORIZATION_RULES = {
    # Keywords (lowercase) : Category
    # --- Food & Drink ---
    'uber eats': 'Food Delivery',
    'real cdn superstore': 'Groceries',
    'valley supermarket': 'Groceries',
    'jj bakes company': 'Dining Out/Cafe',
    'tim hortons': 'Dining Out/Cafe',
    'red swan pizza': 'Dining Out/Cafe',
    'starbucks': 'Dining Out/Cafe',
    'mcdonald\'s': 'Dining Out/Cafe', # Escaped apostrophe for regex
    'save on foods': 'Groceries',
    'bvcs food services ltd': 'Dining Out/Cafe', # Might be Subway based on amex
    'subway': 'Dining Out/Cafe',
    'wal-mart': 'Groceries/General Merchandise',
    'eagle landing liquor': 'Alcohol & Bars',
    'stickys candy': 'Snacks/Treats',
    # --- Bills & Utilities ---
    'netflix.com': 'Subscriptions/Entertainment',
    'apple.com/bill': 'Subscriptions/Services',
    'hp *instant ink': 'Subscriptions/Office', # Asterisk as wildcard
    'fido mobile': 'Bills/Utilities',
    'fortisbc energy': 'Bills/Utilities',
    'square one insurance': 'Insurance',
    'icbc': 'Insurance/Vehicle',
    # --- Shopping & Services ---
    'amazon.ca': 'Shopping/Online',
    'temu.com': 'Shopping/Online',
    'cursor, ai': 'Software/Subscriptions',
    'intuitive rehabilitati': 'Healthcare',
    'sp hebron nutrition': 'Healthcare/Supplements',
    'big box outlet store': 'Shopping/General Merchandise',
    'thinkific labs': 'Software/Services',
    # --- Financial & Transfers ---
    'questrade inc': 'Investments',
    'send e-tfr': 'Transfers',
    'cibc mc': 'Credit Card Payment', # Or just 'Transfer' if it is payment to own card
    'td visa': 'Credit Card Payment',
    'payment - thank you': 'Credit Card Payment', # From TD credit card statements
    'membership fee installment': 'Fees/Charges',
    # --- Other ---
    'tree house children': 'Childcare/Education',
    'city of chilliwack': 'Housing', # Could be tax, utility, etc.
    'emp life': 'Housing',
    'cornerstone prk': 'Housing',
}

def assign_category(description):
    """Assigns a category to a transaction based on its description."""
    if not description:
        return None

    desc_lower = description.lower()

    for keyword_pattern, category in CATEGORIZATION_RULES.items():
        regex_pattern = '.*'.join(re.escape(part) for part in keyword_pattern.split('*'))
        if re.search(regex_pattern, desc_lower):
            return category

    return None # Default if no rule matches

def get_defined_categories():
    """Returns a sorted list of unique category names from the rules."""
    categories = set(CATEGORIZATION_RULES.values())
    # Add a common 'Uncategorized' or allow blank option if desired
    # categories.add("Uncategorized")
    return sorted(list(categories))