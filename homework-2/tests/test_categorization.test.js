const request = require('supertest');
const { classify } = require('../src/services/classifier');
const { createApp } = require('../src/app');
const { TicketRepository } = require('../src/repository/ticketRepository');

const ticket = (subject, description) => ({ subject, description });

describe('classification engine', () => {
  it('detects account_access issues', () => {
    const result = classify(
      ticket('Login problem', 'My password is rejected and 2FA never arrives.')
    );
    expect(result.category).toBe('account_access');
    expect(result.keywords).toEqual(expect.arrayContaining(['login', 'password', '2fa']));
  });

  it('detects billing_question issues', () => {
    const result = classify(
      ticket('Wrong invoice', 'I was charged twice, please issue a refund.')
    );
    expect(result.category).toBe('billing_question');
  });

  it('detects feature_request issues', () => {
    const result = classify(
      ticket('Dark mode', 'It would be great if you could please add a dark theme.')
    );
    expect(result.category).toBe('feature_request');
  });

  it('classifies errors without reproduction steps as technical_issue', () => {
    const result = classify(
      ticket('App crash', 'The app shows an error and crashes when I open settings.')
    );
    expect(result.category).toBe('technical_issue');
  });

  it('upgrades errors with reproduction markers to bug_report', () => {
    const withMarker = classify(
      ticket('App crash', 'Steps to reproduce: open settings, tap save. The app crashes with an error.')
    );
    expect(withMarker.category).toBe('bug_report');

    const withNumberedSteps = classify(
      ticket('Broken export', 'The export fails every time.\n1. open report\n2. click export\nExpected: file downloads. Actual: error 500.')
    );
    expect(withNumberedSteps.category).toBe('bug_report');
    expect(withNumberedSteps.keywords).toContain('numbered steps');
  });

  it('falls back to other with low confidence when nothing matches', () => {
    const result = classify(
      ticket('Hello', 'Just wanted to say your support team is lovely.')
    );
    expect(result.category).toBe('other');
    expect(result.confidence).toBeLessThanOrEqual(0.3);
    expect(result.reasoning).toContain('no category keywords matched');
  });

  it('assigns priority by keywords and defaults to medium', () => {
    expect(classify(ticket('Down', 'Production down, this is critical!')).priority).toBe('urgent');
    expect(classify(ticket('Blocked', 'This is blocking our team, fix asap.')).priority).toBe('high');
    expect(classify(ticket('Typo', 'A minor cosmetic issue in the footer.')).priority).toBe('low');
    expect(classify(ticket('Question', 'How do I export my data to PDF format?')).priority).toBe('medium');
  });

  it('resolves priority keyword conflicts by match count, ties to the higher level', () => {
    // 2 low matches ("minor", "cosmetic") vs 1 urgent ("critical") -> low wins on count
    const countWins = classify(
      ticket('Mixed', 'A minor cosmetic glitch, though the wording calls it critical.')
    );
    expect(countWins.priority).toBe('low');

    // 1 urgent ("security") vs 1 low ("minor") -> tie goes to the higher level
    const tie = classify(ticket('Mixed', 'A minor issue with the security page.'));
    expect(tie.priority).toBe('urgent');
  });

  it('computes confidence within [0.3, 0.95], penalized by competing categories', () => {
    const clean = classify(
      ticket('Login', 'I cannot sign in, my password fails and 2FA is locked out.')
    );
    const mixed = classify(
      ticket('Login', 'My password fails with an error, maybe a billing charge issue too.')
    );
    for (const r of [clean, mixed]) {
      expect(r.confidence).toBeGreaterThanOrEqual(0.3);
      expect(r.confidence).toBeLessThanOrEqual(0.95);
    }
    expect(clean.confidence).toBeGreaterThan(mixed.confidence);
  });

  it('applies results via the API and honors manual override semantics', async () => {
    const app = createApp({ repository: new TicketRepository() });
    const payload = {
      customer_email: 'a@b.com',
      subject: 'Cannot log in',
      description: 'My password is rejected, I cannot access my account. Critical!',
    };

    // auto_classify on create: no manual values -> applied, overridden=false
    const auto = (await request(app).post('/tickets?auto_classify=true').send(payload)).body;
    expect(auto.category).toBe('account_access');
    expect(auto.priority).toBe('urgent');
    expect(auto.classification.overridden).toBe(false);
    expect(auto.classification.confidence).toBeGreaterThanOrEqual(0.3);

    // manual category wins; classifier still fills priority
    const manual = (
      await request(app)
        .post('/tickets?auto_classify=true')
        .send({ ...payload, category: 'billing_question' })
    ).body;
    expect(manual.category).toBe('billing_question');
    expect(manual.priority).toBe('urgent');
    expect(manual.classification.overridden).toBe(true);

    // explicit endpoint always applies and resets overridden
    const reclassified = (
      await request(app).post(`/tickets/${manual.id}/auto-classify`)
    ).body;
    expect(reclassified.category).toBe('account_access');
    expect(reclassified.classification.overridden).toBe(false);

    // later manual PUT flips overridden back on
    const putRes = (
      await request(app).put(`/tickets/${reclassified.id}`).send({ priority: 'low' })
    ).body;
    expect(putRes.classification.overridden).toBe(true);

    // unknown ticket -> 404
    expect((await request(app).post('/tickets/nope/auto-classify')).status).toBe(404);
  });
});
