// Deterministic generator for the sample data deliverables:
//   sample_tickets.csv (50), sample_tickets.json (20), sample_tickets.xml (30)
// plus invalid counterparts for negative tests.
// Run: node demo/generate-samples.js

const fs = require('fs');
const path = require('path');

const OUT = __dirname;

const TEMPLATES = [
  {
    subject: 'Cannot log into my account',
    description:
      'My password is rejected every time and I cannot access my account. This is critical for my work.',
    tags: ['auth', 'login'],
    source: 'web_form',
    device: 'desktop',
  },
  {
    subject: '2FA code never arrives',
    description:
      'The two-factor authentication SMS never arrives, so I am locked out of the login page.',
    tags: ['auth', '2fa'],
    source: 'email',
    device: 'mobile',
  },
  {
    subject: 'Dashboard crashes on load',
    description:
      'The analytics dashboard crashes with an error each time it loads. It worked fine last week.',
    tags: ['crash'],
    source: 'web_form',
    device: 'desktop',
  },
  {
    subject: 'Export fails with reproduction steps',
    description:
      'Steps to reproduce: 1. open the monthly report 2. click export. Expected: a PDF downloads. Actual: an error page appears.',
    tags: ['export', 'bug'],
    source: 'api',
    device: 'desktop',
  },
  {
    subject: 'Charged twice this month',
    description:
      'My invoice shows a duplicate payment. Please issue a refund for the second charge asap, this is important.',
    tags: ['billing'],
    source: 'email',
    device: 'mobile',
  },
  {
    subject: 'Question about subscription price',
    description:
      'Could you explain the price difference between the annual and monthly subscription on my invoice?',
    tags: ['billing'],
    source: 'chat',
    device: 'tablet',
  },
  {
    subject: 'Please add dark mode',
    description:
      'It would be great if you could please add a dark theme. Just a suggestion, purely cosmetic.',
    tags: ['ui', 'idea'],
    source: 'web_form',
    device: 'mobile',
  },
  {
    subject: 'Feature: export to Excel',
    description:
      'Please add an enhancement to export reports directly to Excel. This would improve our workflow a lot.',
    tags: ['export', 'idea'],
    source: 'chat',
    device: 'desktop',
  },
  {
    subject: 'Production down after update',
    description:
      'Production down since the last update, every request fails with an error. Critical, our whole team is blocked.',
    tags: ['outage'],
    source: 'phone',
    device: 'desktop',
  },
  {
    subject: 'Minor typo on the welcome page',
    description:
      'There is a minor cosmetic typo in the greeting banner on the welcome page. Not urgent at all.',
    tags: ['ui'],
    source: 'web_form',
    device: 'tablet',
  },
  {
    subject: 'How do I invite teammates?',
    description:
      'I could not find where to invite my teammates to the workspace. Where is that option located?',
    tags: [],
    source: 'chat',
    device: 'mobile',
  },
  {
    subject: 'Security concern with shared links',
    description:
      'Shared links seem to be readable without a login. This looks like a security problem, please verify.',
    tags: ['security'],
    source: 'email',
    device: 'desktop',
  },
];

const NAMES = [
  'Alice Johnson',
  'Bohdan Kovalenko',
  'Carol Smith',
  'Dmytro Bondar',
  'Emma Wilson',
  'Frank Miller',
  'Halyna Tkachenko',
  'Ivan Petrov',
  'Julia Brown',
  'Kateryna Shevchenko',
];

function record(i) {
  const t = TEMPLATES[i % TEMPLATES.length];
  const name = NAMES[i % NAMES.length];
  const login = name.toLowerCase().replace(/[^a-z]+/g, '.');
  return {
    customer_id: `CUST-${1000 + i}`,
    customer_email: `${login}${i}@example.com`,
    customer_name: name,
    subject: t.subject,
    description: t.description,
    tags: t.tags,
    metadata: { source: t.source, device_type: t.device, browser: i % 3 === 0 ? 'Chrome' : i % 3 === 1 ? 'Firefox' : 'Safari' },
  };
}

// ---------- CSV ----------

const csvEscape = (value) => {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function toCsv(records) {
  const header = 'customer_id,customer_email,customer_name,subject,description,tags,metadata';
  const rows = records.map((r) =>
    [
      r.customer_id,
      r.customer_email,
      r.customer_name,
      r.subject,
      r.description,
      JSON.stringify(r.tags),
      JSON.stringify(r.metadata),
    ]
      .map(csvEscape)
      .join(',')
  );
  return `${header}\n${rows.join('\n')}\n`;
}

// ---------- XML ----------

const xmlEscape = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function toXml(records) {
  const tickets = records
    .map(
      (r) => `  <ticket>
    <customer_id>${xmlEscape(r.customer_id)}</customer_id>
    <customer_email>${xmlEscape(r.customer_email)}</customer_email>
    <customer_name>${xmlEscape(r.customer_name)}</customer_name>
    <subject>${xmlEscape(r.subject)}</subject>
    <description>${xmlEscape(r.description)}</description>
    <tags>
${r.tags.map((t) => `      <tag>${xmlEscape(t)}</tag>`).join('\n') || '      '}
    </tags>
    <metadata>
      <source>${r.metadata.source}</source>
      <device_type>${r.metadata.device_type}</device_type>
      <browser>${r.metadata.browser}</browser>
    </metadata>
  </ticket>`
    )
    .join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<tickets>\n${tickets}\n</tickets>\n`;
}

// ---------- generate ----------

const write = (name, content) => {
  fs.writeFileSync(path.join(OUT, name), content);
  console.log(`wrote ${name}`);
};

const range = (n, offset = 0) => Array.from({ length: n }, (_, i) => record(i + offset));

write('sample_tickets.csv', toCsv(range(50)));
write('sample_tickets.json', `${JSON.stringify(range(20, 50), null, 2)}\n`);
write('sample_tickets.xml', toXml(range(30, 70)));

// ---------- invalid counterparts (each mixes valid and broken records) ----------

const broken = [
  { ...record(0), customer_email: 'not-an-email' },
  { ...record(1), subject: '' },
  { ...record(2), description: 'too short' },
];

write('invalid_tickets.csv', toCsv([record(3), broken[0], broken[2]]));
write(
  'invalid_tickets.json',
  `${JSON.stringify([record(4), { ...record(5), priority: 'someday' }, broken[1]], null, 2)}\n`
);
write('invalid_tickets.xml', toXml([record(6), broken[0], broken[2]]));
