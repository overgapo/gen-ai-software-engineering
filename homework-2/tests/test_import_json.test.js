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

describe('JSON import', () => {
  it('imports a valid JSON array and applies defaults', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('valid.json'));
    expect(res.status).toBe(201);
    expect(res.body).toEqual({ total: 2, successful: 2, failed: 0, errors: [] });

    const [eve] = repository.list({ search: 'charged twice' });
    expect(eve).toMatchObject({ category: 'other', priority: 'medium', status: 'new' });
    expect(eve.id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('preserves nested tags and metadata from JSON records', async () => {
    await request(app).post('/tickets/import').attach('file', fixture('valid.json'));
    const [dan] = repository.list({ search: 'crashes' });
    expect(dan.tags).toEqual(['crash']);
    expect(dan.metadata).toEqual({ source: 'email', device_type: 'mobile' });
  });

  it('rejects JSON that is not an array', async () => {
    const res = await request(app)
      .post('/tickets/import')
      .attach('file', Buffer.from('{"customer_email":"a@b.com"}'), 'single.json');
    expect(res.status).toBe(400);
    expect(res.body.reason).toContain('array');
  });

  it('rejects syntactically malformed JSON', async () => {
    const res = await request(app)
      .post('/tickets/import')
      .attach('file', Buffer.from('[{"customer_email": broken'), 'broken.json');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Import failed');
  });

  it('is all-or-nothing for invalid records', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('invalid.json'));
    expect(res.status).toBe(400);
    expect(res.body).toMatchObject({ total: 2, successful: 0, failed: 1 });
    expect(res.body.errors[0].record).toBe(2);
    expect(repository.count()).toBe(0);
  });
});
