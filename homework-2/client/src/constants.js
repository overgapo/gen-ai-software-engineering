export const CATEGORIES = [
  'account_access',
  'technical_issue',
  'billing_question',
  'feature_request',
  'bug_report',
  'other',
];

export const PRIORITIES = ['urgent', 'high', 'medium', 'low'];

export const STATUSES = ['new', 'in_progress', 'waiting_customer', 'resolved', 'closed'];

export const SOURCES = ['web_form', 'email', 'api', 'chat', 'phone'];

export const DEVICE_TYPES = ['desktop', 'mobile', 'tablet'];

export const label = (value) =>
  value
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ');
