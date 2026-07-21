const request = require('supertest');
const { createApp } = require('../src/app');
const { TicketRepository } = require('../src/repository/ticketRepository');

// Task 6 scenarios, exercised end to end through the HTTP layer only.

const TEXTS = [
  ['Cannot log in', 'My password is rejected and I cannot access my account.'],
  ['App error', 'The dashboard crashes with an error when loading reports.'],
  ['Repro bug', 'Steps to reproduce: 1. open settings 2. click save. Expected: saved. Actual: error.'],
  ['Double charge', 'I was charged twice, please refund the duplicate payment.'],
  ['Add exports', 'It would be great if you could please add CSV exports.'],
  ['Thanks', 'Just wanted to thank the support team for the quick help.'],
];

const csvOf = (rows) =>
  `customer_email,subject,description\n${rows
    .map(
      ([subject, description], i) =>
        `user${i}@example.com,${subject},"${description.replace(/"/g, '""')}"`
    )
    .join('\n')}\n`;

let app;
let repository;

beforeEach(() => {
  repository = new TicketRepository();
  app = createApp({ repository });
});

describe('end-to-end workflows (Task 6)', () => {
  it('runs the complete ticket lifecycle from creation to deletion', async () => {
    const created = (
      await request(app).post('/tickets?auto_classify=true').send({
        customer_email: 'e2e@example.com',
        subject: 'Cannot access my account',
        description: 'Login fails with a security error. Production down for our team!',
      })
    ).body;
    expect(created.category).toBe('account_access');
    expect(created.priority).toBe('urgent');
    expect(created.classification.overridden).toBe(false);

    const assigned = (
      await request(app)
        .put(`/tickets/${created.id}`)
        .send({ status: 'in_progress', assigned_to: 'agent-42' })
    ).body;
    expect(assigned).toMatchObject({ status: 'in_progress', assigned_to: 'agent-42' });

    await request(app).put(`/tickets/${created.id}`).send({ status: 'waiting_customer' });
    const resolved = (
      await request(app).put(`/tickets/${created.id}`).send({ status: 'resolved' })
    ).body;
    expect(resolved.resolved_at).not.toBeNull();

    const closed = (
      await request(app).put(`/tickets/${created.id}`).send({ status: 'closed' })
    ).body;
    expect(closed.resolved_at).toBe(resolved.resolved_at);

    await request(app).delete(`/tickets/${created.id}`).expect(204);
    expect((await request(app).get('/tickets')).body).toHaveLength(0);
  });

  it('bulk imports 30 tickets with auto-classification and verifies every result', async () => {
    const rows = Array.from({ length: 30 }, (_, i) => TEXTS[i % TEXTS.length]);
    const res = await request(app)
      .post('/tickets/import?auto_classify=true')
      .attach('file', Buffer.from(csvOf(rows)), 'bulk.csv');
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ total: 30, successful: 30, failed: 0 });

    const all = (await request(app).get('/tickets')).body;
    expect(all).toHaveLength(30);
    for (const ticket of all) {
      expect(ticket.classification).not.toBeNull();
      expect(ticket.classification.confidence).toBeGreaterThan(0);
      expect(ticket.classification.overridden).toBe(false);
    }

    // 6 texts cycled 5 times -> exactly 5 tickets per expected category
    for (const category of [
      'account_access',
      'technical_issue',
      'bug_report',
      'billing_question',
      'feature_request',
      'other',
    ]) {
      const filtered = (await request(app).get(`/tickets?category=${category}`)).body;
      expect(filtered).toHaveLength(5);
    }
  });

  it('stays consistent under 20+ concurrent mixed operations', async () => {
    const seed = (
      await request(app).post('/tickets').send({
        customer_email: 'seed@example.com',
        subject: 'Seed ticket',
        description: 'Ticket used as the target of concurrent operations.',
      })
    ).body;

    const results = await Promise.all([
      ...Array.from({ length: 10 }, (_, i) =>
        request(app).post('/tickets').send({
          customer_email: `c${i}@example.com`,
          subject: `Concurrent ${i}`,
          description: 'Created while other requests are in flight.',
        })
      ),
      ...Array.from({ length: 5 }, () => request(app).get('/tickets')),
      ...Array.from({ length: 3 }, () => request(app).post(`/tickets/${seed.id}/auto-classify`)),
      ...Array.from({ length: 3 }, (_, i) =>
        request(app).put(`/tickets/${seed.id}`).send({ assigned_to: `agent-${i}` })
      ),
    ]);

    for (const res of results) {
      expect([200, 201]).toContain(res.status);
    }

    const all = (await request(app).get('/tickets')).body;
    expect(all).toHaveLength(11);
    const seedAfter = (await request(app).get(`/tickets/${seed.id}`)).body;
    expect(seedAfter.classification).not.toBeNull();
    expect(['agent-0', 'agent-1', 'agent-2']).toContain(seedAfter.assigned_to);
  });

  it('serves combined category and priority filters over imported data', async () => {
    const rows = [
      ['Login failure', 'I cannot access my account, this is critical and blocking.'],
      ['Login hiccup', 'Sign in works but the login page shows a minor cosmetic glitch.'],
      ['Refund now', 'Duplicate payment, refund needed asap, this is blocking and important.'],
      ['Invoice typo', 'A minor typo on my invoice, just a suggestion to fix the label.'],
    ];
    await request(app)
      .post('/tickets/import?auto_classify=true')
      .attach('file', Buffer.from(csvOf(rows)), 'filters.csv')
      .expect(201);

    const urgentAccess = (
      await request(app).get('/tickets?category=account_access&priority=urgent')
    ).body;
    expect(urgentAccess).toHaveLength(1);
    expect(urgentAccess[0].subject).toBe('Login failure');

    const lowAccess = (
      await request(app).get('/tickets?category=account_access&priority=low')
    ).body;
    expect(lowAccess).toHaveLength(1);
    expect(lowAccess[0].subject).toBe('Login hiccup');

    const highBilling = (
      await request(app).get('/tickets?category=billing_question&priority=high')
    ).body;
    expect(highBilling).toHaveLength(1);
    expect(highBilling[0].subject).toBe('Refund now');

    expect(
      (await request(app).get('/tickets?category=bug_report&priority=urgent')).body
    ).toHaveLength(0);
  });
});
