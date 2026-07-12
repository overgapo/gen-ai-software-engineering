const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');
const { findChrome } = require('./chrome');

const PORT = 3100;
const BASE = `http://localhost:${PORT}`;
const ROOT = path.join(__dirname, '..', '..');
const fixture = (name) => path.join(ROOT, 'tests', 'fixtures', name);

const chromePath = findChrome();
// Without a local Chrome the suite skips instead of failing (CI portability).
const maybeDescribe = chromePath ? describe : describe.skip;
if (!chromePath) {
  console.warn('tests/ui: no Chrome found, skipping. Set CHROME_PATH to enable.');
}

let server;
let browser;
let page;

const seedImport = async (name) => {
  const form = new FormData();
  form.append('file', new Blob([fs.readFileSync(fixture(name))]), name);
  const res = await fetch(`${BASE}/tickets/import?auto_classify=true`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`seed import failed: ${await res.text()}`);
};

const cardCount = () => page.$$eval('.ticket-card', (els) => els.length);
const clickByText = (selector, text) =>
  page.evaluate(
    (sel, txt) => {
      const el = [...document.querySelectorAll(sel)].find((e) => e.textContent.trim() === txt);
      if (!el) throw new Error(`element not found: ${sel} with text "${txt}"`);
      el.click();
    },
    selector,
    text
  );
const waitForToast = () => page.waitForSelector('.toast', { timeout: 5000 });

maybeDescribe('web UI end-to-end', () => {
  beforeAll(async () => {
    // NODE_ENV=test disables the disk snapshot -> hermetic run
    server = spawn('node', [path.join(ROOT, 'src', 'server.js')], {
      env: { ...process.env, PORT: String(PORT), NODE_ENV: 'test' },
      stdio: 'ignore',
    });
    let up = false;
    for (let i = 0; i < 50 && !up; i++) {
      try {
        up = (await fetch(`${BASE}/health`)).ok;
      } catch {
        await new Promise((r) => setTimeout(r, 200));
      }
    }
    if (!up) throw new Error('server did not start');

    await seedImport('valid.csv'); // 3 tickets

    browser = await puppeteer.launch({ executablePath: chromePath, headless: 'new' });
    page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 900 });
    await page.goto(BASE, { waitUntil: 'networkidle0' });
  }, 60000);

  afterAll(async () => {
    if (browser) await browser.close();
    if (server) server.kill();
  });

  it('renders the seeded ticket list', async () => {
    await page.waitForSelector('.ticket-card');
    expect(await cardCount()).toBe(3);
    expect(await page.$eval('body', (b) => b.textContent)).toContain('Cannot login');
  });

  it('opens the detail panel with the classification block on card click', async () => {
    await page.click('.ticket-card');
    await page.waitForSelector('.detail');
    const detailText = await page.$eval('.detail', (d) => d.textContent);
    expect(detailText).toContain('Classification');
    expect(detailText).toContain('Confidence');
    expect(await page.$('.confidence-fill')).not.toBeNull();
    await clickByText('.detail button', '✕');
  });

  it('narrows the list with combined category and priority filters', async () => {
    await page.select('select[aria-label="categories"]', 'billing_question');
    await page.select('select[aria-label="priorities"]', 'high');
    await page.waitForFunction(
      () => document.querySelectorAll('.ticket-card').length === 1
    );
    expect(await page.$eval('.ticket-subject', (s) => s.textContent)).toBe('Refund request');
    await page.select('select[aria-label="categories"]', '');
    await page.select('select[aria-label="priorities"]', '');
  });

  it('narrows the list with free-text search', async () => {
    await page.type('input[type=search]', 'dark mode');
    await page.waitForFunction(
      () => document.querySelectorAll('.ticket-card').length === 1
    );
    expect(await page.$eval('.ticket-subject', (s) => s.textContent)).toBe('Feature idea');
    await page.evaluate(() => {
      const input = document.querySelector('input[type=search]');
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      ).set;
      setter.call(input, '');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await page.waitForFunction(
      () => document.querySelectorAll('.ticket-card').length === 3
    );
  });

  it('blocks form submission on client-side validation errors', async () => {
    await clickByText('button', 'New ticket');
    await page.waitForSelector('.modal');
    await page.type('.modal input', 'not-an-email');
    await page.type('.modal textarea', 'short');
    await clickByText('.modal button', 'Create ticket');
    await page.waitForSelector('.field-error');
    const errors = await page.$$eval('.field-error', (els) => els.map((e) => e.textContent));
    expect(errors).toHaveLength(3); // email, subject, description
    expect(await cardCount()).toBe(3); // nothing created
    await clickByText('.modal button', 'Cancel');
  });

  it('creates an auto-classified ticket through the form', async () => {
    await clickByText('button', 'New ticket');
    await page.waitForSelector('.modal');
    await page.type('.modal input', 'e2e@example.com');
    const inputs = await page.$$('.modal input.input');
    await inputs[2].type('Cannot access my account at all'); // subject (0=email, 1=name)
    await page.type('.modal textarea', 'The login page rejects my password. Critical for our team!');
    await clickByText('.modal button', 'Create ticket');
    await waitForToast();
    await page.waitForSelector('.detail');
    const detailText = await page.$eval('.detail', (d) => d.textContent);
    expect(detailText).toContain('Account Access');
    expect(detailText).toContain('Urgent');
    expect(await cardCount()).toBe(4);
  });

  it('imports a valid file through the dialog and reports the summary', async () => {
    await clickByText('button', 'Import');
    await page.waitForSelector('.modal');
    const fileInput = await page.$('.modal input[type=file]');
    await fileInput.uploadFile(fixture('valid.xml'));
    await clickByText('.modal button', 'Import');
    await page.waitForSelector('.modal .banner-success');
    const banner = await page.$eval('.modal .banner-success', (b) => b.textContent);
    expect(banner).toContain('Imported 2 of 2');
    await clickByText('.modal button', 'Close');
    await page.waitForFunction(
      () => document.querySelectorAll('.ticket-card').length === 6
    );
  });

  it('shows per-record errors and imports nothing on an invalid file', async () => {
    const before = await cardCount();
    await clickByText('button', 'Import');
    await page.waitForSelector('.modal');
    const fileInput = await page.$('.modal input[type=file]');
    await fileInput.uploadFile(fixture('invalid.csv'));
    await clickByText('.modal button', 'Import');
    await page.waitForSelector('.modal .banner-error');
    const banner = await page.$eval('.modal .banner-error', (b) => b.textContent);
    expect(banner).toContain('nothing was imported');
    expect(banner).toContain('customer_email');
    await clickByText('.modal button', 'Close');
    expect(await cardCount()).toBe(before);
  });

  it('re-classifies from the detail panel and reflects the override lifecycle', async () => {
    await page.click('.ticket-card');
    await page.waitForSelector('.detail');
    await clickByText('.detail button', 'Auto-classify');
    await waitForToast();
    const detailText = await page.$eval('.detail', (d) => d.textContent);
    expect(detailText).toContain('Classified at');
  });

  it('sets and clears the resolved timestamp via the status dropdown', async () => {
    await page.waitForSelector('.detail');
    await page.select('.detail select', 'resolved');
    await page.waitForFunction(() =>
      /Resolved(?!.*—)/.test(document.querySelector('.detail').textContent)
    );
    let detailText = await page.$eval('.detail', (d) => d.textContent);
    expect(detailText).not.toMatch(/Resolved—/);

    await page.select('.detail select', 'in_progress');
    await page.waitForFunction(() =>
      document.querySelector('.detail').textContent.includes('Resolved—')
    );
  });

  // regression: a dead API used to surface the raw "Failed to fetch"
  it('shows a helpful error toast when the API is unreachable', async () => {
    server.kill();
    await new Promise((r) => setTimeout(r, 500));
    // click a card that is not currently selected, so a fetch is triggered
    await page.click('.ticket-card:not(.is-selected)');
    await page.waitForSelector('.toast-error', { timeout: 5000 });
    const toast = await page.$eval('.toast-error', (t) => t.textContent);
    expect(toast).toContain('Cannot reach the server');
  });
});
