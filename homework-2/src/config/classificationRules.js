// Keyword tables for the rule-based classifier. All matching is
// case-insensitive substring search over subject + description.

const CATEGORY_KEYWORDS = {
  account_access: [
    'login',
    'log in',
    'sign in',
    'password',
    '2fa',
    'two-factor',
    'locked out',
    'authentication',
    'access my account',
  ],
  technical_issue: [
    'error',
    'crash',
    'bug',
    'broken',
    'not working',
    'fails',
    'failure',
    'freezes',
    'timeout',
    'slow',
  ],
  billing_question: [
    'payment',
    'invoice',
    'refund',
    'charged',
    'charge',
    'billing',
    'subscription',
    'receipt',
    'price',
  ],
  feature_request: [
    'feature',
    'enhancement',
    'would be great',
    'please add',
    'improve',
    'wish',
    'idea',
  ],
};

// bug_report is technical_issue + evidence of reproduction steps (SPEC §5).
const REPRO_MARKERS = [
  'steps to reproduce',
  'to reproduce',
  'reproduce',
  'expected behavior',
  'actual behavior',
  'expected:',
  'actual:',
];

// A numbered list ("1. open the app") also counts as reproduction steps.
const NUMBERED_STEPS_RE = /(?:^|\n)\s*\d+[.)]\s+\S/;

const PRIORITY_KEYWORDS = {
  urgent: ["can't access", 'cannot access', 'critical', 'production down', 'security'],
  high: ['important', 'blocking', 'asap'],
  low: ['minor', 'cosmetic', 'suggestion'],
};

// Tie-break order for equal priority match counts: higher wins.
const PRIORITY_ORDER = ['urgent', 'high', 'low'];

module.exports = {
  CATEGORY_KEYWORDS,
  REPRO_MARKERS,
  NUMBERED_STEPS_RE,
  PRIORITY_KEYWORDS,
  PRIORITY_ORDER,
};
