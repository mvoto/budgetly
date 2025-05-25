# Budgetly

A personal budgeting application built with Python and Flask that helps you track expenses, categorize transactions, and manage budgets with multi-user authentication.

## Features

- **User Authentication**: Secure registration and login system
- **Transaction Management**: Upload CSV files or manually add transactions
- **Smart Categorization**: Automatic transaction categorization with customizable rules
- **Budget Tracking**: Set and monitor monthly budgets by category
- **Multi-User Support**: Complete data isolation between users
- **Interactive Dashboard**: Visual charts and spending analytics
- **CSV Upload**: Support for multiple bank CSV formats
- **Responsive Design**: Modern, mobile-friendly interface

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd budgetly
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # venv\Scripts\activate   # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**
   ```bash
   flask init-db
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

   The application will be available at `http://localhost:5001`

## Authentication

The application includes a complete authentication system:

- **Registration**: Create new user accounts with email/password
- **Login/Logout**: Secure session management
- **Password Security**: Passwords are hashed using bcrypt
- **Data Isolation**: Each user can only access their own data
- **CSRF Protection**: Forms are protected against cross-site request forgery

## Testing

### Prerequisites

Make sure you have the testing dependencies installed:
```bash
pip install pytest pytest-flask pytest-cov
```

### Running Tests

#### Run All Tests
```bash
pytest tests/
```

#### Run Tests with Verbose Output
```bash
pytest tests/ -v
```

#### Run Tests with Coverage Report
```bash
pytest tests/ --cov=. --cov-report=html
```

#### Run Specific Test Files
```bash
# Authentication tests
pytest tests/test_auth.py -v

# Category management tests
pytest tests/test_categories.py -v

# Transaction tests
pytest tests/test_transactions.py -v

# File upload tests
pytest tests/test_file_upload.py -v

# Budget tests
pytest tests/test_budgets.py -v
```

#### Run Specific Test Classes or Methods
```bash
# Run specific test class
pytest tests/test_auth.py::TestUserRegistration -v

# Run specific test method
pytest tests/test_auth.py::TestUserRegistration::test_successful_registration -v
```

### Test Coverage

The test suite includes comprehensive coverage for:

- **Authentication** (15 tests): Registration, login, logout, session management
- **Categories** (16 tests): CRUD operations, rules management, data isolation
- **Transactions** (13 tests): CRUD operations, sorting, data isolation, duplicate handling
- **File Upload** (16 tests): CSV processing, security, error handling, categorization
- **Budgets** (13 tests): Budget management, validation, data isolation
- **Integration** (16 tests): Cross-feature functionality and security

**Total: 89 tests** covering all major functionality and security features.

### Test Configuration

Tests use:
- **Isolated test database**: Each test runs with a clean database
- **Test fixtures**: Automated user creation and authentication
- **Mocked file uploads**: Safe testing of file upload functionality
- **CSRF disabled**: For easier testing (enabled in production)

### Running Tests in CI/CD

The test suite is designed to run in continuous integration environments:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests with exit code for CI
pytest tests/ --tb=short

# Generate coverage report for CI
pytest tests/ --cov=. --cov-report=xml --cov-report=term
```

## Development

### Database Migrations

If you make changes to the database models:

```bash
# Initialize migration repository (first time only)
flask db init

# Create a new migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade
```

### Adding Default Categories

For new users, you can add default expense categories:

```bash
flask create-default-categories
```

### Environment Variables

Create a `.env` file for configuration:
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///budgetly.db
```

## File Upload Support

The application supports CSV uploads from various banks. Supported formats:
- TD Bank
- CIBC
- Generic CSV with Date, Description, Amount columns

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass: `pytest tests/`
5. Submit a pull request

## Security Features

- Password hashing with bcrypt
- Session-based authentication
- CSRF protection on all forms
- SQL injection prevention with SQLAlchemy ORM
- User data isolation
- Secure file upload handling

## License

This project is licensed under the MIT License.

# Upcoming Features

