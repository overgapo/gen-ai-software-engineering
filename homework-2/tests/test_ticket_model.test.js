const { validateCreate, validateUpdate } = require('../src/validation/ticket');

const validPayload = {
  customer_email: 'jane@example.com',
  subject: 'Cannot log in',
  description: 'I cannot log into my account since yesterday.',
};

describe('ticket validation', () => {
  it('accepts a minimal payload with only required fields', () => {
    const { errors, value } = validateCreate(validPayload);
    expect(errors).toEqual([]);
    expect(value).toEqual(validPayload);
  });

  it('reports every missing required field', () => {
    const { errors } = validateCreate({});
    const fields = errors.map((e) => e.field);
    expect(fields).toEqual(
      expect.arrayContaining(['customer_email', 'subject', 'description'])
    );
    expect(errors).toHaveLength(3);
  });

  it('rejects malformed email addresses', () => {
    for (const bad of ['not-an-email', 'a@b', 'a b@c.com', 42, null]) {
      const { errors } = validateCreate({ ...validPayload, customer_email: bad });
      expect(errors).toEqual([
        { field: 'customer_email', message: expect.stringContaining('valid email') },
      ]);
    }
  });

  it('enforces subject length of 1-200 characters', () => {
    expect(validateCreate({ ...validPayload, subject: '' }).errors).toHaveLength(1);
    expect(validateCreate({ ...validPayload, subject: 'x'.repeat(201) }).errors).toHaveLength(1);
    expect(validateCreate({ ...validPayload, subject: 'x'.repeat(200) }).errors).toEqual([]);
  });

  it('enforces description length of 10-2000 characters', () => {
    expect(validateCreate({ ...validPayload, description: 'too short' }).errors).toHaveLength(1);
    expect(validateCreate({ ...validPayload, description: 'x'.repeat(2001) }).errors).toHaveLength(1);
    expect(validateCreate({ ...validPayload, description: 'x'.repeat(2000) }).errors).toEqual([]);
  });

  it('rejects unknown enum values for category, priority, and status', () => {
    const { errors } = validateCreate({
      ...validPayload,
      category: 'spam',
      priority: 'immediately',
      status: 'done',
    });
    expect(errors.map((e) => e.field).sort()).toEqual(['category', 'priority', 'status']);
    for (const error of errors) {
      expect(error.message).toContain('must be one of');
    }
  });

  it('validates tags and nested metadata fields', () => {
    const { errors } = validateCreate({
      ...validPayload,
      tags: ['ok', 7],
      metadata: { source: 'carrier_pigeon', device_type: 'toaster', browser: '' },
    });
    expect(errors.map((e) => e.field).sort()).toEqual([
      'metadata.browser',
      'metadata.device_type',
      'metadata.source',
      'tags',
    ]);

    const good = validateCreate({
      ...validPayload,
      tags: ['vpn'],
      metadata: { source: 'email', device_type: 'mobile', browser: 'Firefox' },
    });
    expect(good.errors).toEqual([]);
    expect(good.value.metadata).toEqual({
      source: 'email',
      device_type: 'mobile',
      browser: 'Firefox',
    });
  });

  it('treats update validation as partial: subset ok, invalid values still rejected', () => {
    expect(validateUpdate({ status: 'resolved' }).errors).toEqual([]);
    expect(validateUpdate({}).errors).toEqual([]);
    expect(validateUpdate({ priority: 'nope' }).errors).toEqual([
      { field: 'priority', message: expect.stringContaining('must be one of') },
    ]);
    expect(validateUpdate({ customer_email: 'broken' }).errors).toHaveLength(1);
  });

  it('silently ignores server-managed fields on create and update', () => {
    const serverManaged = {
      id: 'client-chosen-id',
      created_at: '2020-01-01T00:00:00.000Z',
      updated_at: '2020-01-01T00:00:00.000Z',
      resolved_at: '2020-01-01T00:00:00.000Z',
      classification: { confidence: 1 },
    };
    const created = validateCreate({ ...validPayload, ...serverManaged });
    expect(created.errors).toEqual([]);
    for (const field of Object.keys(serverManaged)) {
      expect(created.value).not.toHaveProperty(field);
    }
    const updated = validateUpdate(serverManaged);
    expect(updated.errors).toEqual([]);
    expect(updated.value).toEqual({});
  });
});
