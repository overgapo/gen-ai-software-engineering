const crypto = require('crypto');
const express = require('express');
const store = require('./store');
const { validateExpense } = require('./validation');

const router = express.Router();

// API key guarding destructive operations. Read from the environment — never hardcode a
// secret in source. If unset, the DELETE route fails closed (see the handler below).
const API_KEY = process.env.API_KEY;

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
    result = result.filter((e) => Date.parse(e.date) <= to);
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
  // Reuse the shared filter so the summary always describes the same set GET /expenses
  // returns for the same query.
  const rows = filterExpenses(store.all(), req.query);
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

  if (!API_KEY || typeof provided !== 'string') {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const providedBuf = Buffer.from(provided);
  const expectedBuf = Buffer.from(API_KEY);
  const authorized =
    providedBuf.length === expectedBuf.length &&
    crypto.timingSafeEqual(providedBuf, expectedBuf);

  if (!authorized) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const removed = store.remove(Number(req.params.id));
  if (!removed) {
    return res.status(404).json({ error: 'Expense not found' });
  }
  return res.status(204).send();
});

module.exports = { router, filterExpenses };
