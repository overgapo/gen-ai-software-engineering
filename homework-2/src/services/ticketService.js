const crypto = require('crypto');
const { ACTIVE_STATUSES } = require('../config/enums');

const RESOLVED_STATUSES = ['resolved', 'closed'];

function buildTicket(value) {
  const now = new Date().toISOString();
  const status = value.status ?? 'new';
  return {
    id: crypto.randomUUID(),
    customer_id: value.customer_id ?? null,
    customer_email: value.customer_email,
    customer_name: value.customer_name ?? null,
    subject: value.subject,
    description: value.description,
    category: value.category ?? 'other',
    priority: value.priority ?? 'medium',
    status,
    created_at: now,
    updated_at: now,
    resolved_at: RESOLVED_STATUSES.includes(status) ? now : null,
    assigned_to: value.assigned_to ?? null,
    tags: value.tags ?? [],
    metadata: { source: 'api', ...(value.metadata ?? {}) },
    classification: null,
  };
}

function applyUpdate(existing, value) {
  const now = new Date().toISOString();
  const updated = { ...existing, ...value, updated_at: now };

  if (value.metadata) {
    updated.metadata = { ...existing.metadata, ...value.metadata };
  }

  if (value.status && value.status !== existing.status) {
    if (RESOLVED_STATUSES.includes(value.status) && !existing.resolved_at) {
      updated.resolved_at = now;
    } else if (ACTIVE_STATUSES.includes(value.status)) {
      updated.resolved_at = null;
    }
  }

  if (existing.classification && (value.category || value.priority)) {
    updated.classification = { ...existing.classification, overridden: true };
  }

  return updated;
}

module.exports = { buildTicket, applyUpdate };
