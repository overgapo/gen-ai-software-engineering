const request = require('supertest');
const { createApp } = require('../src/app');
const { TicketRepository } = require('../src/repository/ticketRepository');
const { buildTicket } = require('../src/services/ticketService');
const { classify } = require('../src/services/classifier');

// Thresholds from SPEC §6 — generous by design to avoid flaky CI runs.
const time = async (fn) => {
  const start = process.hrtime.bigint();
  await fn();
  return Number(process.hrtime.bigint() - start) / 1e6; // ms
};

const payload = (i = 0) => ({
  customer_email: `user${i}@example.com`,
  subject: `Ticket number ${i}`,
  description: 'A description that is long enough to pass validation checks.',
});

let app;
let repository;

beforeEach(() => {
  repository = new TicketRepository();
  app = createApp({ repository });
});

describe('performance benchmarks', () => {
  it('creates a single ticket in < 50ms', async () => {
    // warm-up: the very first request pays express/supertest cold-start costs
    await request(app).post('/tickets').send(payload(9999)).expect(201);
    const samples = [];
    for (let i = 0; i < 5; i++) {
      samples.push(await time(() => request(app).post('/tickets').send(payload(i)).expect(201)));
    }
    const median = samples.sort((a, b) => a - b)[2];
    expect(median).toBeLessThan(50);
  });

  it('lists 1000 tickets in < 200ms', async () => {
    repository.createMany(
      Array.from({ length: 1000 }, (_, i) => buildTicket(payload(i)))
    );
    const ms = await time(async () => {
      const res = await request(app).get('/tickets').expect(200);
      expect(res.body).toHaveLength(1000);
    });
    expect(ms).toBeLessThan(200);
  });

  it('imports 100 CSV records in < 2s', async () => {
    const rows = Array.from(
      { length: 100 },
      (_, i) => `user${i}@example.com,Ticket ${i},A description that is long enough to pass.`
    );
    const csv = `customer_email,subject,description\n${rows.join('\n')}\n`;
    const ms = await time(() =>
      request(app)
        .post('/tickets/import')
        .attach('file', Buffer.from(csv), 'bulk.csv')
        .expect(201)
    );
    expect(repository.count()).toBe(100);
    expect(ms).toBeLessThan(2000);
  });

  it('classifies a ticket in < 20ms', async () => {
    const ticket = {
      subject: 'Cannot log in, production down',
      description:
        'Steps to reproduce: open the login page, enter password, see an error. Critical!',
    };
    const ms = await time(() => classify(ticket));
    expect(ms).toBeLessThan(20);
  });

  it('handles 20 concurrent requests in < 3s total', async () => {
    const seed = (await request(app).post('/tickets').send(payload(999))).body;
    const ops = Array.from({ length: 20 }, (_, i) => {
      switch (i % 4) {
        case 0:
          return request(app).post('/tickets').send(payload(i)).expect(201);
        case 1:
          return request(app).get('/tickets').expect(200);
        case 2:
          return request(app).get(`/tickets/${seed.id}`).expect(200);
        default:
          return request(app).post(`/tickets/${seed.id}/auto-classify`).expect(200);
      }
    });
    const ms = await time(() => Promise.all(ops));
    expect(ms).toBeLessThan(3000);
    expect(repository.count()).toBe(1 + 5); // seed + five POSTs (i = 0,4,8,12,16)
  });
});
