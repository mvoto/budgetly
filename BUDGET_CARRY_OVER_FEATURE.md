# Budget Carry-Over Feature

## Overview

The Budget Carry-Over feature allows users to easily copy their planned budgets by category to upcoming months, eliminating the need to manually set budgets each month.

## Features

- **Bulk Budget Creation**: Copy all budgets from a source month to multiple future months
- **Smart Updates**: Automatically updates existing budgets if they already exist
- **Flexible Range**: Carry over budgets for 1 to 60 months (up to 5 years)
- **User-Friendly Interface**: Simple modal dialog with clear instructions
- **Real-time Feedback**: Shows success/error messages and operation results

## How It Works

### User Interface

1. **Access**: Navigate to the Dashboard and locate the "Carry Over Budgets" button in the Budget Planning section
2. **Configure**: Click the button to open a modal dialog
3. **Set Range**: Enter the number of months to carry over to (1-60)
4. **Execute**: Click "Carry Over Budgets" to start the process
5. **Confirm**: View success message showing how many budgets were created/updated

### Backend Process

1. **Source Validation**: Checks that budgets exist for the current month/year
2. **Target Calculation**: Calculates target months using `dateutil.relativedelta`
3. **Budget Processing**: For each target month and category:
   - Checks if budget already exists
   - Updates existing budget or creates new one
   - Uses the same amount as the source budget
4. **Response**: Returns summary of operations performed

## API Endpoint

### POST `/api/budgets/carry-over`

**Request Body:**
```json
{
  "source_month": 1,
  "source_year": 2024,
  "target_months": 12
}
```

**Response:**
```json
{
  "message": "Successfully carried over budgets for 12 months",
  "budgets_created": 36,
  "budgets_updated": 0,
  "source_month": 1,
  "source_year": 2024,
  "target_months": 12
}
```

**Error Responses:**
- `400`: Invalid parameters (month, year, or target_months out of range)
- `404`: No budgets found for source month/year
- `500`: Server error during processing

## Implementation Details

### Files Modified

1. **`app.py`**: Added `/api/budgets/carry-over` endpoint
2. **`templates/index.html`**: Added carry-over button and modal
3. **`static/css/style.css`**: Added styling for success messages and modal elements
4. **`requirements.txt`**: Added `python-dateutil` dependency
5. **`tests/test_budgets.py`**: Added comprehensive tests

### Key Components

- **API Endpoint**: Handles validation, processing, and response
- **Modal Interface**: User-friendly dialog for configuration
- **JavaScript Functions**: Handle modal display and API communication
- **CSS Styling**: Consistent styling with existing design system

### Security Features

- **Authentication Required**: Uses `@login_required` decorator
- **User Isolation**: Only processes budgets for the current user
- **Input Validation**: Validates all parameters before processing
- **CSRF Protection**: Uses `@csrf.exempt` for API endpoint

## Usage Examples

### Example 1: Setting Up Annual Budgets
```
Source: January 2024 budgets
- Groceries: $500
- Utilities: $200
- Entertainment: $150

Action: Carry over for 12 months
Result: Budgets created for Feb 2024 - Jan 2025
```

### Example 2: Updating Existing Budgets
```
Source: March 2024 budgets (updated amounts)
- Groceries: $600 (increased)
- Utilities: $180 (decreased)

Action: Carry over for 6 months
Result: Existing budgets for Apr-Sep 2024 updated with new amounts
```

## Benefits

- **Time Saving**: No need to manually set budgets each month
- **Consistency**: Ensures consistent budget planning across months
- **Flexibility**: Can update all future months when budget needs change
- **Efficiency**: Bulk operations instead of individual budget setting
- **User Experience**: Simple, intuitive interface

## Testing

The feature includes comprehensive tests covering:

- **Success Cases**: Normal carry-over operations
- **Update Cases**: Updating existing budgets
- **Validation**: Parameter validation and error handling
- **Edge Cases**: No source budgets, invalid parameters
- **Security**: User isolation and authentication

Run tests with:
```bash
python -m pytest tests/test_budgets.py -k "carry_over" -v
```

## Future Enhancements

Potential improvements for future versions:

1. **Selective Carry-Over**: Choose specific categories to carry over
2. **Percentage Adjustments**: Apply percentage increases/decreases during carry-over
3. **Template Budgets**: Save budget templates for different scenarios
4. **Bulk Import**: Import budgets from CSV files
5. **Calendar Integration**: Visual calendar view for budget planning