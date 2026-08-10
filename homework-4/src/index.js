const { createApp } = require('./app');
const store = require('./store');

// Seed a little data so the API returns something meaningful on first run.
// Note: the coffee expense is dated 2026-01-31 on purpose — it sits exactly on the
// upper bound of the demo date-range query and exposes the seeded boundary bug.
store.reset([
  { id: 1, amount: 12.5, category: 'food', date: '2026-01-05', description: 'Lunch' },
  { id: 2, amount: 40.0, category: 'transport', date: '2026-01-10', description: 'Taxi' },
  { id: 3, amount: 8.25, category: 'food', date: '2026-01-31', description: 'Coffee' },
]);

const PORT = process.env.PORT || 3000;
const app = createApp();

app.listen(PORT, () => {
  console.log(`Expense-tracker API listening on http://localhost:${PORT}`);
});
