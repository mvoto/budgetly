from extensions import db
from datetime import date

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    rules = db.relationship('Rule', backref='category', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='category', lazy=True)
    budgets = db.relationship('Budget', backref='category', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Category {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'rules': [rule.to_dict() for rule in self.rules]
        }

class Rule(db.Model):
    __tablename__ = 'rules'
    id = db.Column(db.Integer, primary_key=True)
    keyword_pattern = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

    def __repr__(self):
        return f'<Rule {self.keyword_pattern} (Category ID: {self.category_id})>'

    def to_dict(self):
        return {
            'id': self.id,
            'keyword_pattern': self.keyword_pattern,
            # category_id is not needed here, it's implied by the parent category
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    account_source = db.Column(db.String(50), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)

    def __repr__(self):
        return f'<Transaction {self.date} {self.description} {self.amount}>'

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'description': self.description,
            'amount': self.amount,
            'account_source': self.account_source,
            'category_id': self.category_id
        }

class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    budgeted_amount = db.Column(db.Float, nullable=False, default=0.0)

    # Ensure unique budget per category per month/year
    __table_args__ = (db.UniqueConstraint('category_id', 'month', 'year', name='_category_month_year_uc'),)

    def __repr__(self):
        return f'<Budget {self.category.name if self.category else "No Category"} {self.year}-{self.month:02d} ${self.budgeted_amount}>'

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else 'Unknown',
            'month': self.month,
            'year': self.year,
            'budgeted_amount': self.budgeted_amount
        }