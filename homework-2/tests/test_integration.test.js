const path = require('path');
const request = require('supertest');
const { createApp } = require('../src/app');
const { TicketRepository } = require('../src/repository/ticketRepository');

const fixture = (name) => path.join(__dirname, 'fixtures', name);

let app;
let repository;

beforeEach(() => {
  repository = new TicketRepository();
  app = createApp({ repository });
});

describe('integration workflows', () => {
  it('walks a ticket through its full lifecycle', async () => {
    const created = (
      await request(app).post('/tickets').send({
        customer_email: 'flow@example.com',
        subject: 'Cannot access my account',
        description: 'Login fails with an error after the last update. Critical for us.',
      })
    ).body;
    expect(created.status).toBe('new');

    const classified = (await request(app).post(`/tickets/${created.id}/auto-classify`)).body;
    expect(classified.category).toBe('account_access');
    expect(classified.priority).toBe('urgent');

    const assigned = (
      await request(app).put(`/tickets/${created.id}`).send({ status: 'in_progress', assigned_to: 'agent-1' })
    ).body;
    expect(assigned.assigned_to).toBe('agent-1');
    expect(assigned.resolved_at).toBeNull();

    const resolved = (
      await request(app).put(`/tickets/${created.id}`).send({ status: 'resolved' })
    ).body;
    expect(resolved.resolved_at).not.toBeNull();

    const closed = (
      await request(app).put(`/tickets/${created.id}`).send({ status: 'closed' })
    ).body;
    expect(closed.resolved_at).toBe(resolved.resolved_at);

    await request(app).delete(`/tickets/${created.id}`).expect(204);
    await request(app).get(`/tickets/${created.id}`).expect(404);
  });

  it('imports a file and serves it through combined filters', async () => {
    await request(app).post('/tickets/import').attach('file', fixture('valid.csv')).expect(201);

    const combined = await request(app).get('/tickets?category=billing_question&priority=high');
    expect(combined.body).toHaveLength(1);
    expect(combined.body[0].customer_email).toBe('bob@example.com');

    const none = await request(app).get('/tickets?category=billing_question&priority=low');
    expect(none.body).toHaveLength(0);
  });

  it('verifies auto-classification of a bulk import end to end', async () => {
    await request(app)
      .post('/tickets/import?auto_classify=true')
      .attach('file', fixture('valid.json'))
      .expect(201);

    const bugReports = await request(app).get('/tickets?category=bug_report');
    expect(bugReports.body).toHaveLength(1);
    expect(bugReports.body[0].classification).toMatchObject({ overridden: false });
    expect(bugReports.body[0].classification.confidence).toBeGreaterThanOrEqual(0.3);

    const billing = await request(app).get('/tickets?category=billing_question');
    expect(billing.body).toHaveLength(1);
  });

  it('searches across a mix of created and imported tickets', async () => {
    await request(app).post('/tickets/import').attach('file', fixture('valid.xml')).expect(201);
    await request(app).post('/tickets').send({
      customer_email: 'mix@example.com',
      subject: 'Password expired',
      description: 'My password expired and the reset email never arrives.',
    });

    const search = await request(app).get('/tickets?search=password');
    expect(search.body).toHaveLength(2);

    const searchAndStatus = await request(app).get('/tickets?search=password&status=new');
    expect(searchAndStatus.body).toHaveLength(2);
  });

  it('failed operations leave state untouched', async () => {
    const created = (
      await request(app).post('/tickets').send({
        customer_email: 'safe@example.com',
        subject: 'Baseline',
        description: 'This ticket must not change on failed requests.',
      })
    ).body;

    await request(app)
      .put(`/tickets/${created.id}`)
      .send({ status: 'nope', priority: 'urgent' })
      .expect(400);
    const after = (await request(app).get(`/tickets/${created.id}`)).body;
    expect(after).toEqual(created);

    await request(app).post('/tickets/import').attach('file', fixture('invalid.csv')).expect(400);
    expect((await request(app).get('/tickets')).body).toHaveLength(1);
  });
});
