const request = require('supertest');
const { createApp } = require('../src/app');
const store = require('../src/store');

// Fixed fixture, independent of src/index.js's demo seed. `id: 3` sits exactly on the
// `to` bound used below (2026-01-31) to target the seeded boundary bug (context/bugs/002).
const FIXTURE = [
  { id: 1, amount: 12.5, category: 'food', date: '2026-01-05', description: 'Lunch' },
  { id: 2, amount: 40.0, category: 'transport', date: '2026-01-10', description: 'Taxi' },
  { id: 3, amount: 8.25, category: 'food', date: '2026-01-31', description: 'Coffee' },
];

describe('GET /summary (context/bugs/001 — filtered summary must match filtered list)', () => {
  let app;

  beforeEach(() => {
    store.reset(FIXTURE);
    app = createApp();
  });

  test('unfiltered summary aggregates every record', async () => {
    const res = await request(app).get('/summary');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(3);
    expect(res.body.total).toBe(60.75);
  });

  test('filtered summary equals the aggregate of the matching filtered list, and differs from the unfiltered total', async () => {
    const unfiltered = await request(app).get('/summary');
    const filtered = await request(app).get('/summary?category=food');

    expect(filtered.status).toBe(200);
    // Filtered set is the two food records: 12.50 + 8.25 = 20.75 (matches GET /expenses?category=food).
    expect(filtered.body.count).toBe(2);
    expect(filtered.body.total).toBe(20.75);
    expect(filtered.body.byCategory).toEqual({ food: 20.75 });
    // The whole point of the fix: a filtered summary must not silently equal the unfiltered one.
    expect(filtered.body.total).not.toBe(unfiltered.body.total);
  });
});

describe('GET /expenses date-range filter (context/bugs/002 — `to` bound must be inclusive)', () => {
  let app;

  beforeEach(() => {
    store.reset(FIXTURE);
    app = createApp();
  });

  test('a record dated exactly on the `to` bound is included in the range', async () => {
    const res = await request(app).get('/expenses?from=2026-01-01&to=2026-01-31');
    expect(res.status).toBe(200);
    const ids = res.body.map((e) => e.id).sort();
    // id 3 is dated 2026-01-31, exactly the `to` value — must be returned, not dropped.
    expect(ids).toEqual([1, 2, 3]);
  });

  test('a record one day after the `to` bound is still excluded', async () => {
    const res = await request(app).get('/expenses?from=2026-01-01&to=2026-01-30');
    expect(res.status).toBe(200);
    const ids = res.body.map((e) => e.id).sort();
    expect(ids).toEqual([1, 2]);
  });
});

describe('DELETE /expenses/:id authorization (context/bugs/003 — env secret + constant-time compare)', () => {
  let app;
  const ORIGINAL_API_KEY = process.env.API_KEY;

  beforeEach(() => {
    store.reset(FIXTURE);
    app = createApp();
    // Deliberately not the seeded literal from src/expenses.js — this is the key the
    // fixed implementation is expected to read from the environment.
    process.env.API_KEY = 'test-only-secret-does-not-appear-in-src';
  });

  afterEach(() => {
    if (ORIGINAL_API_KEY === undefined) {
      delete process.env.API_KEY;
    } else {
      process.env.API_KEY = ORIGINAL_API_KEY;
    }
  });

  test('the key configured via process.env.API_KEY authorizes deletion', async () => {
    const res = await request(app)
      .delete('/expenses/1')
      .set('x-api-key', process.env.API_KEY);
    expect(res.status).toBe(204);
    expect(store.getById(1)).toBeUndefined();
  });

  test('a wrong key is rejected with 401 and the record is not removed', async () => {
    const res = await request(app)
      .delete('/expenses/2')
      .set('x-api-key', 'wrong-key');
    expect(res.status).toBe(401);
    expect(store.getById(2)).toBeDefined();
  });

  test('a missing key header is rejected with 401', async () => {
    const res = await request(app).delete('/expenses/3');
    expect(res.status).toBe(401);
    expect(store.getById(3)).toBeDefined();
  });
});
