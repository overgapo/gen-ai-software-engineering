const {
  CATEGORIES,
  PRIORITIES,
  STATUSES,
  SOURCES,
  DEVICE_TYPES,
} = require('../config/enums');

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const oneOf = (allowed) => (v) =>
  allowed.includes(v) ? null : `must be one of: ${allowed.join(', ')}`;

const optionalString = (v) =>
  typeof v === 'string' && v.length > 0 ? null : 'must be a non-empty string';

const boundedString = (min, max) => (v) =>
  typeof v === 'string' && v.length >= min && v.length <= max
    ? null
    : `must be a string of ${min}-${max} characters`;

// Server-managed fields (id, created_at, updated_at, resolved_at,
// classification) are never copied into `value` — clients cannot set them.
function validateTicket(payload, { partial = false } = {}) {
  const errors = [];
  const value = {};

  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    return {
      errors: [{ field: 'body', message: 'request body must be a JSON object' }],
      value,
    };
  }

  const check = (field, validate, { required = false } = {}) => {
    if (payload[field] === undefined) {
      if (required && !partial) errors.push({ field, message: 'is required' });
      return;
    }
    const message = validate(payload[field]);
    if (message) errors.push({ field, message });
    else value[field] = payload[field];
  };

  check(
    'customer_email',
    (v) => (typeof v === 'string' && EMAIL_RE.test(v) ? null : 'must be a valid email address'),
    { required: true }
  );
  check('subject', boundedString(1, 200), { required: true });
  check('description', boundedString(10, 2000), { required: true });
  check('customer_id', optionalString);
  check('customer_name', optionalString);
  check('category', oneOf(CATEGORIES));
  check('priority', oneOf(PRIORITIES));
  check('status', oneOf(STATUSES));
  check('assigned_to', (v) =>
    v === null || (typeof v === 'string' && v.length > 0)
      ? null
      : 'must be a non-empty string or null'
  );
  check('tags', (v) =>
    Array.isArray(v) && v.every((t) => typeof t === 'string')
      ? null
      : 'must be an array of strings'
  );

  if (payload.metadata !== undefined) {
    const meta = payload.metadata;
    if (meta === null || typeof meta !== 'object' || Array.isArray(meta)) {
      errors.push({ field: 'metadata', message: 'must be an object' });
    } else {
      const sanitized = {};
      const metaChecks = [
        ['source', oneOf(SOURCES)],
        ['browser', optionalString],
        ['device_type', oneOf(DEVICE_TYPES)],
      ];
      for (const [field, validate] of metaChecks) {
        if (meta[field] === undefined) continue;
        const message = validate(meta[field]);
        if (message) errors.push({ field: `metadata.${field}`, message });
        else sanitized[field] = meta[field];
      }
      if (!errors.some((e) => e.field.startsWith('metadata'))) {
        value.metadata = sanitized;
      }
    }
  }

  return { errors, value };
}

const validateCreate = (payload) => validateTicket(payload);
const validateUpdate = (payload) => validateTicket(payload, { partial: true });

module.exports = { validateCreate, validateUpdate };
