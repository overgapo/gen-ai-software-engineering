// In-memory expense store. No database — data lives only for the process lifetime.
// Kept as a tiny module so both the running server and the tests can share (and reset) it.

let expenses = [];
let nextId = 1;

// Replace the store contents, e.g. to seed demo data or give each test a clean slate.
function reset(seed = []) {
  expenses = seed.map((e) => ({ ...e }));
  nextId = expenses.reduce((max, e) => Math.max(max, e.id || 0), 0) + 1;
}

function all() {
  return expenses;
}

function getById(id) {
  return expenses.find((e) => e.id === id);
}

function add(expense) {
  const record = { id: nextId++, ...expense };
  expenses.push(record);
  return record;
}

function remove(id) {
  const idx = expenses.findIndex((e) => e.id === id);
  if (idx === -1) return false;
  expenses.splice(idx, 1);
  return true;
}

module.exports = { reset, all, getById, add, remove };
