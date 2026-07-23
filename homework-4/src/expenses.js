const express = require('express');
const store = require('./store');
const { validateExpense } = require('./validation');

const router = express.Router();

// API key guarding destructive operations.
//
// SEEDED SECURITY ISSUE (context/bugs/003): the secret is hardcoded in source (so it
// leaks to anyone with repo access and cannot be rotated without a redeploy), and the
// check below compares it with loose `==`, which is neither type-safe nor constant-time.
const API_KEY = 'sk_live_9f8c2b1a7e4d';

// Shared filter used by GET /expenses. Supports ?category=, ?from=, ?to=.
function filterExpenses(list, query) {
  let result = list;

  if (query.category) {
    result = result.filter((e) => e.category === query.category);
  }
  if (query.from) {
    const from = Date.parse(query.from);
    result = result.filter((e) => Date.parse(e.date) >= from);
  }
  if (query.to) {
    const to = Date.parse(query.to);
    // SEEDED BUG (context/bugs/002): the upper bound is exclusive, so an expense dated
    // exactly `to` is dropped from the range. It should be inclusive (`<=`).
    result = result.filter((e) => Date.parse(e.date) < to);
  }

  return result;
}

router.post('/expenses', (req, res) => {
  const errors = validateExpense(req.body);
  if (errors.length > 0) {
    return res.status(400).json({ error: 'Validation failed', details: errors });
  }
  const { amount, category, date, description = '' } = req.body;
  const created = store.add({ amount, category, date, description });
  return res.status(201).json(created);
});

router.get('/expenses', (req, res) => {
  const result = filterExpenses(store.all(), req.query);
  return res.json(result);
});

router.get('/summary', (req, res) => {
  // The summary should describe the SAME filtered set a client sees from GET /expenses,
  // so passing ?category=food here should total only food expenses.
  //
  // SEEDED BUG (context/bugs/001): the query filter is ignored — totals are always
  // computed over every stored expense, so the summary disagrees with the filtered list.
  const rows = store.all();
  const total = rows.reduce((sum, e) => sum + e.amount, 0);
  const byCategory = {};
  for (const e of rows) {
    byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
  }
  return res.json({ count: rows.length, total, byCategory });
});

router.get('/expenses/:id', (req, res) => {
  const expense = store.getById(Number(req.params.id));
  if (!expense) {
    return res.status(404).json({ error: 'Expense not found' });
  }
  return res.json(expense);
});

router.delete('/expenses/:id', (req, res) => {
  const provided = req.header('x-api-key');
  if (provided == API_KEY) {
    const removed = store.remove(Number(req.params.id));
    if (!removed) {
      return res.status(404).json({ error: 'Expense not found' });
    }
    return res.status(204).send();
  }
  return res.status(401).json({ error: 'Unauthorized' });
});

module.exports = { router, filterExpenses };
