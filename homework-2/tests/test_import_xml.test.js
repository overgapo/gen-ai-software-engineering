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

describe('XML import', () => {
  it('imports valid XML with nested tags and metadata', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('valid.xml'));
    expect(res.status).toBe(201);
    expect(res.body).toEqual({ total: 2, successful: 2, failed: 0, errors: [] });

    const [frank] = repository.list({ search: 'password reset' });
    expect(frank.tags).toEqual(['auth', 'loop']);
    expect(frank.metadata).toEqual({
      source: 'web_form',
      device_type: 'tablet',
      browser: 'Safari',
    });
  });

  it('imports a file with a single <ticket> element', async () => {
    const single = `<tickets><ticket>
      <customer_email>solo@example.com</customer_email>
      <subject>Only one</subject>
      <description>A single ticket inside the XML file.</description>
    </ticket></tickets>`;
    const res = await request(app)
      .post('/tickets/import')
      .attach('file', Buffer.from(single), 'single.xml');
    expect(res.status).toBe(201);
    expect(res.body.successful).toBe(1);
  });

  it('rejects syntactically malformed XML', async () => {
    const res = await request(app)
      .post('/tickets/import')
      .attach('file', Buffer.from('<tickets><ticket><subject>oops</tickets>'), 'broken.xml');
    expect(res.status).toBe(400);
    expect(res.body.reason).toContain('invalid XML');
  });

  it('rejects XML without <tickets><ticket> elements', async () => {
    const res = await request(app)
      .post('/tickets/import')
      .attach('file', Buffer.from('<records><item>x</item></records>'), 'wrong.xml');
    expect(res.status).toBe(400);
    expect(res.body.reason).toContain('<tickets>');
  });

  it('is all-or-nothing for invalid records', async () => {
    const res = await request(app).post('/tickets/import').attach('file', fixture('invalid.xml'));
    expect(res.status).toBe(400);
    expect(res.body).toMatchObject({ total: 2, successful: 0, failed: 1 });
    expect(repository.count()).toBe(0);
  });
});
