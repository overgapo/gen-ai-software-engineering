const request = require('supertest');
const { createApp } = require('../src/app');
const { TicketRepository } = require('../src/repository/ticketRepository');

const payload = (overrides = {}) => ({
  customer_email: 'jane@example.com',
  subject: 'Cannot log in',
  description: 'I cannot log into my account since yesterday.',
  ...overrides,
});

let app;

beforeEach(() => {
  app = createApp({ repository: new TicketRepository() });
});

describe('ticket CRUD API', () => {
  it('POST /tickets creates a ticket with server-generated fields and defaults', async () => {
    const res = await request(app).post('/tickets').send(payload());
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({
      customer_email: 'jane@example.com',
      category: 'other',
      priority: 'medium',
      status: 'new',
      assigned_to: null,
      resolved_at: null,
      tags: [],
      metadata: { source: 'api' },
      classification: null,
    });
    expect(res.body.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(res.body.created_at).toBe(res.body.updated_at);
  });

  it('POST /tickets rejects an invalid payload with structured details', async () => {
    const res = await request(app)
      .post('/tickets')
      .send({ customer_email: 'nope', description: 'short' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Validation failed');
    expect(res.body.details.map((d) => d.field).sort()).toEqual([
      'customer_email',
      'description',
      'subject',
    ]);
  });

  it('rejects a malformed JSON body with 400', async () => {
    const res = await request(app)
      .post('/tickets')
      .set('Content-Type', 'application/json')
      .send('{"subject": broken');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid JSON body');
  });

  it('GET /tickets returns all tickets newest-first', async () => {
    for (const subject of ['first', 'second', 'third']) {
      await request(app).post('/tickets').send(payload({ subject }));
    }
    const res = await request(app).get('/tickets');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(3);
    const created = res.body.map((t) => t.created_at);
    expect([...created].sort().reverse()).toEqual(created);
  });

  it('GET /tickets applies single and combined AND filters', async () => {
    await request(app).post('/tickets').send(payload({ category: 'billing_question', priority: 'high', subject: 'refund please' }));
    await request(app).post('/tickets').send(payload({ category: 'billing_question', priority: 'low' }));
    await request(app).post('/tickets').send(payload({ category: 'technical_issue', priority: 'high' }));

    const byCategory = await request(app).get('/tickets?category=billing_question');
    expect(byCategory.body).toHaveLength(2);

    const combined = await request(app).get('/tickets?category=billing_question&priority=high');
    expect(combined.body).toHaveLength(1);
    expect(combined.body[0].subject).toBe('refund please');

    const bySearch = await request(app).get('/tickets?search=REFUND');
    expect(bySearch.body).toHaveLength(1);
  });

  it('GET /tickets rejects unknown enum filter values', async () => {
    const res = await request(app).get('/tickets?category=spam&priority=nope');
    expect(res.status).toBe(400);
    expect(res.body.details.map((d) => d.field).sort()).toEqual(['category', 'priority']);
  });

  it('GET /tickets/:id returns the ticket or 404', async () => {
    const created = await request(app).post('/tickets').send(payload());
    const found = await request(app).get(`/tickets/${created.body.id}`);
    expect(found.status).toBe(200);
    expect(found.body).toEqual(created.body);

    const missing = await request(app).get('/tickets/does-not-exist');
    expect(missing.status).toBe(404);
    expect(missing.body.error).toBe('Ticket not found');
  });

  it('PUT /tickets/:id merges a partial update and refreshes updated_at only', async () => {
    const created = (await request(app).post('/tickets').send(payload())).body;
    const res = await request(app)
      .put(`/tickets/${created.id}`)
      .send({ priority: 'high', assigned_to: 'agent-7', id: 'hacker', created_at: 'hacker' });
    expect(res.status).toBe(200);
    expect(res.body.priority).toBe('high');
    expect(res.body.assigned_to).toBe('agent-7');
    expect(res.body.subject).toBe(created.subject);
    expect(res.body.id).toBe(created.id);
    expect(res.body.created_at).toBe(created.created_at);
    expect(res.body.updated_at >= created.updated_at).toBe(true);
  });

  it('PUT manages resolved_at across status transitions', async () => {
    const created = (await request(app).post('/tickets').send(payload())).body;

    const resolved = await request(app).put(`/tickets/${created.id}`).send({ status: 'resolved' });
    expect(resolved.body.resolved_at).not.toBeNull();

    const closed = await request(app).put(`/tickets/${created.id}`).send({ status: 'closed' });
    expect(closed.body.resolved_at).toBe(resolved.body.resolved_at);

    const reopened = await request(app).put(`/tickets/${created.id}`).send({ status: 'in_progress' });
    expect(reopened.body.resolved_at).toBeNull();
  });

  it('PUT rejects invalid values and unknown ids', async () => {
    const created = (await request(app).post('/tickets').send(payload())).body;
    const invalid = await request(app).put(`/tickets/${created.id}`).send({ status: 'done' });
    expect(invalid.status).toBe(400);
    expect(invalid.body.details[0].field).toBe('status');

    const missing = await request(app).put('/tickets/does-not-exist').send({ status: 'closed' });
    expect(missing.status).toBe(404);
  });

  it('DELETE /tickets/:id removes the ticket and 404s on unknown ids', async () => {
    const created = (await request(app).post('/tickets').send(payload())).body;
    const del = await request(app).delete(`/tickets/${created.id}`);
    expect(del.status).toBe(204);

    expect((await request(app).get(`/tickets/${created.id}`)).status).toBe(404);
    expect((await request(app).delete(`/tickets/${created.id}`)).status).toBe(404);
  });
});
