const request = require('supertest');
const { createApp } = require('../src/app');
const store = require('../src/store');

const SEED = [
  { id: 1, amount: 12.5, category: 'food', date: '2026-01-05', description: 'Lunch' },
  { id: 2, amount: 40.0, category: 'transport', date: '2026-01-10', description: 'Taxi' },
  { id: 3, amount: 8.25, category: 'food', date: '2026-01-31', description: 'Coffee' },
];

describe('GET /summary respects query filters (Bug #1 fix)', () => {
  let app;

  beforeEach(() => {
    store.reset(SEED);
    app = createApp();
  });

  test('filtered summary equals the aggregate of the matching filtered list', async () => {
    const list = await request(app).get('/expenses').query({ category: 'food' });
    const summary = await request(app).get('/summary').query({ category: 'food' });

    expect(summary.status).toBe(200);
    const expectedTotal = list.body.reduce((sum, e) => sum + e.amount, 0);
    expect(summary.body.count).toBe(list.body.length);
    expect(summary.body.total).toBe(expectedTotal);
    expect(summary.body.total).toBe(20.75);
    expect(summary.body.byCategory).toEqual({ food: 20.75 });
  });

  test('filtered summary total differs from the unfiltered total', async () => {
    const unfiltered = await request(app).get('/summary');
    const filtered = await request(app).get('/summary').query({ category: 'food' });

    expect(unfiltered.body.total).toBe(60.75);
    expect(filtered.body.total).toBe(20.75);
    expect(filtered.body.total).not.toBe(unfiltered.body.total);
  });
});

describe('date-range filter includes the upper bound (Bug #2 fix)', () => {
  let app;

  beforeEach(() => {
    store.reset(SEED);
    app = createApp();
  });

  test('a record dated exactly on the `to` bound is returned', async () => {
    const res = await request(app)
      .get('/expenses')
      .query({ from: '2026-01-01', to: '2026-01-31' });

    expect(res.status).toBe(200);
    const ids = res.body.map((e) => e.id).sort();
    expect(ids).toEqual([1, 2, 3]);
    expect(res.body.some((e) => e.date === '2026-01-31')).toBe(true);
  });

  test('a record dated exactly on the `to` bound is included in the summary too', async () => {
    const res = await request(app)
      .get('/summary')
      .query({ from: '2026-01-01', to: '2026-01-31' });

    expect(res.status).toBe(200);
    expect(res.body.count).toBe(3);
    expect(res.body.total).toBe(60.75);
  });
});

describe('DELETE /expenses/:id authorization (Security fix #3)', () => {
  // src/expenses.js reads API_KEY into a module-level constant at require time, so each
  // test must reset Jest's module registry and re-require before setting the env var —
  // otherwise every test would share whatever value was captured on first import.
  const ORIGINAL_API_KEY = process.env.API_KEY;
  const TEST_KEY = 'test-only-key-do-not-hardcode-elsewhere';

  function freshAppWithKey(apiKey) {
    jest.resetModules();
    if (apiKey === undefined) {
      delete process.env.API_KEY;
    } else {
      process.env.API_KEY = apiKey;
    }
    const freshStore = require('../src/store');
    freshStore.reset(SEED);
    const { createApp: freshCreateApp } = require('../src/app');
    return { app: freshCreateApp(), store: freshStore };
  }

  afterEach(() => {
    if (ORIGINAL_API_KEY === undefined) {
      delete process.env.API_KEY;
    } else {
      process.env.API_KEY = ORIGINAL_API_KEY;
    }
    jest.resetModules();
  });

  test('correct key (read from env) authorizes the delete', async () => {
    const { app, store: freshStore } = freshAppWithKey(TEST_KEY);
    const res = await request(app).delete('/expenses/1').set('x-api-key', TEST_KEY);

    expect(res.status).toBe(204);
    expect(freshStore.getById(1)).toBeUndefined();
  });

  test('wrong key is rejected with 401 and the record is not removed', async () => {
    const { app, store: freshStore } = freshAppWithKey(TEST_KEY);
    const res = await request(app).delete('/expenses/1').set('x-api-key', 'wrong-key');

    expect(res.status).toBe(401);
    expect(freshStore.getById(1)).toBeDefined();
  });

  test('missing header is rejected with 401', async () => {
    const { app, store: freshStore } = freshAppWithKey(TEST_KEY);
    const res = await request(app).delete('/expenses/1');

    expect(res.status).toBe(401);
    expect(freshStore.getById(1)).toBeDefined();
  });

  test('unset API_KEY fails closed with 401 even when a header is provided', async () => {
    const { app, store: freshStore } = freshAppWithKey(undefined);
    const res = await request(app).delete('/expenses/1').set('x-api-key', 'anything');

    expect(res.status).toBe(401);
    expect(freshStore.getById(1)).toBeDefined();
  });
});

describe('amount validation accepts genuine two-decimal values (Bug #4 fix)', () => {
  let app;

  beforeEach(() => {
    store.reset([]);
    app = createApp();
  });

  test.each([8.29, 19.99, 0.07, 12.5])(
    'accepts %p as a valid two-decimal amount',
    async (amount) => {
      const res = await request(app)
        .post('/expenses')
        .send({ amount, category: 'food', date: '2026-02-01' });

      expect(res.status).toBe(201);
      expect(res.body.amount).toBe(amount);
    }
  );

  test('still rejects an over-precise amount (boundary: three decimal places)', async () => {
    const res = await request(app)
      .post('/expenses')
      .send({ amount: 1.005, category: 'food', date: '2026-02-01' });

    expect(res.status).toBe(400);
    expect(res.body.details.some((d) => d.field === 'amount')).toBe(true);
  });

  test('still rejects a non-positive amount', async () => {
    const res = await request(app)
      .post('/expenses')
      .send({ amount: -5, category: 'food', date: '2026-02-01' });

    expect(res.status).toBe(400);
    expect(res.body.details.some((d) => d.field === 'amount')).toBe(true);
  });
});
