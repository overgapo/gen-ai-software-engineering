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

describe('CSV import', () => {
  it('imports a valid CSV file and returns the summary', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('valid.csv'));
    expect(res.status).toBe(201);
    expect(res.body).toEqual({ total: 3, successful: 3, failed: 0, errors: [] });
    expect(repository.count()).toBe(3);
  });

  it('parses JSON-in-cell tags and metadata columns', async () => {
    await request(app).post('/tickets/import').attach('file', fixture('valid.csv'));
    const [alice] = repository.list({ search: 'cannot login' });
    expect(alice.tags).toEqual(['auth', 'login']);
    expect(alice.metadata).toEqual({
      source: 'web_form',
      device_type: 'desktop',
      browser: 'Chrome',
    });
  });

  it('is all-or-nothing: one invalid record rejects the whole file', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('invalid.csv'));
    expect(res.status).toBe(400);
    expect(res.body).toMatchObject({ error: 'Import failed', total: 3, successful: 0, failed: 1 });
    expect(repository.count()).toBe(0);
  });

  it('reports per-record errors with record number and field details', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('invalid.csv'));
    expect(res.body.errors).toHaveLength(1);
    const [error] = res.body.errors;
    expect(error.record).toBe(2);
    expect(error.details.map((d) => d.field)).toEqual(
      expect.arrayContaining(['customer_email', 'description', 'category'])
    );
  });

  it('rejects a structurally malformed CSV file', async () => {
    const malformed = 'customer_email,subject\n"unterminated quote,oops\nx,y,z,extra';
    const res = await request(app)
      .post('/tickets/import')
      .attach('file', Buffer.from(malformed), 'broken.csv');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Import failed');
    expect(repository.count()).toBe(0);
  });

  it('auto-classifies imported tickets when auto_classify=true', async () => {
    const res = await request(app)
      .post('/tickets/import?auto_classify=true')
      .attach('file', fixture('valid.csv'));
    expect(res.status).toBe(201);

    const [alice] = repository.list({ search: 'cannot login' });
    expect(alice.category).toBe('account_access');
    expect(alice.classification).not.toBeNull();

    // manual category in the file wins, classification recorded as overridden
    const [bob] = repository.list({ search: 'refund' });
    expect(bob.category).toBe('billing_question');
    expect(bob.classification.overridden).toBe(true);
  });
});
