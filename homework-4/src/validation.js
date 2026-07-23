// Validation for incoming expense payloads. Returns an array of { field, message }
// errors (empty array means valid), so the route can shape a 400 response.

function validateExpense(body) {
  const errors = [];
  const { amount, category, date } = body || {};

  if (typeof amount !== 'number' || Number.isNaN(amount)) {
    errors.push({ field: 'amount', message: 'amount must be a number' });
  } else if (amount <= 0) {
    errors.push({ field: 'amount', message: 'amount must be positive' });
  } else if (!hasAtMostTwoDecimals(amount)) {
    errors.push({ field: 'amount', message: 'amount must have at most 2 decimal places' });
  }

  if (typeof category !== 'string' || category.trim() === '') {
    errors.push({ field: 'category', message: 'category is required' });
  }

  if (typeof date !== 'string' || Number.isNaN(Date.parse(date))) {
    errors.push({ field: 'date', message: 'date must be an ISO 8601 date string' });
  }

  return errors;
}

function hasAtMostTwoDecimals(n) {
  return Math.round(n * 100) === n * 100;
}

module.exports = { validateExpense };
