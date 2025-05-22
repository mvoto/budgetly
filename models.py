from extensions import db # Import db instance from extensions.py
from sqlalchemy import func

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    # Amount: positive for income/credits, negative for expenses/debits
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='CAD') # Default to CAD
    account_source = db.Column(db.String(50), nullable=False) # e.g., 'TD Chequing', 'Amex', 'CIBC Manual'
    category = db.Column(db.String(50), nullable=True) # Optional category
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f'<Transaction {self.id} {self.date} {self.description} {self.amount}>'