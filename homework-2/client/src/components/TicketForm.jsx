import { useState } from 'react';
import { CATEGORIES, PRIORITIES, STATUSES, SOURCES, label } from '../constants';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Mirrors the server-side rules from SPEC §2 for instant feedback;
// the server remains the source of truth.
function validate(values) {
  const errors = {};
  if (!EMAIL_RE.test(values.customer_email)) {
    errors.customer_email = 'Enter a valid email address';
  }
  if (values.subject.length < 1 || values.subject.length > 200) {
    errors.subject = 'Subject must be 1-200 characters';
  }
  if (values.description.length < 10 || values.description.length > 2000) {
    errors.description = 'Description must be 10-2000 characters';
  }
  return errors;
}

export default function TicketForm({ ticket, onSave, onCancel }) {
  const editing = Boolean(ticket);
  const [values, setValues] = useState({
    customer_email: ticket?.customer_email ?? '',
    customer_name: ticket?.customer_name ?? '',
    subject: ticket?.subject ?? '',
    description: ticket?.description ?? '',
    category: ticket?.category ?? 'other',
    priority: ticket?.priority ?? 'medium',
    status: ticket?.status ?? 'new',
    assigned_to: ticket?.assigned_to ?? '',
    tags: (ticket?.tags ?? []).join(', '),
    source: ticket?.metadata?.source ?? 'web_form',
  });
  const [autoClassify, setAutoClassify] = useState(!editing);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [saving, setSaving] = useState(false);

  const set = (field) => (e) => setValues((v) => ({ ...v, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    const validation = validate(values);
    setErrors(validation);
    if (Object.keys(validation).length) return;

    const payload = {
      customer_email: values.customer_email,
      subject: values.subject,
      description: values.description,
      category: values.category,
      priority: values.priority,
      status: values.status,
      tags: values.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      metadata: { source: values.source },
    };
    if (values.customer_name) payload.customer_name = values.customer_name;
    payload.assigned_to = values.assigned_to || null;

    // let auto-classification pick these on create
    if (!editing && autoClassify) {
      delete payload.category;
      delete payload.priority;
    }

    setSaving(true);
    setServerError(null);
    try {
      await onSave(payload, { autoClassify: !editing && autoClassify });
    } catch (err) {
      const details = err.body?.details
        ?.map((d) => `${d.field} ${d.message}`)
        .join('; ');
      setServerError(details || err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h2>{editing ? 'Edit ticket' : 'New ticket'}</h2>

        {serverError && <div className="banner banner-error">{serverError}</div>}

        <label className="field">
          Customer email *
          <input className="input" value={values.customer_email} onChange={set('customer_email')} />
          {errors.customer_email && <span className="field-error">{errors.customer_email}</span>}
        </label>

        <label className="field">
          Customer name
          <input className="input" value={values.customer_name} onChange={set('customer_name')} />
        </label>

        <label className="field">
          Subject *
          <input className="input" value={values.subject} onChange={set('subject')} maxLength={200} />
          {errors.subject && <span className="field-error">{errors.subject}</span>}
        </label>

        <label className="field">
          Description * <span className="muted">({values.description.length}/2000)</span>
          <textarea
            className="input"
            rows={4}
            value={values.description}
            onChange={set('description')}
            maxLength={2000}
          />
          {errors.description && <span className="field-error">{errors.description}</span>}
        </label>

        {!editing && (
          <label className="field field-inline">
            <input
              type="checkbox"
              checked={autoClassify}
              onChange={(e) => setAutoClassify(e.target.checked)}
            />
            Auto-classify category and priority
          </label>
        )}

        {(editing || !autoClassify) && (
          <div className="field-row">
            <label className="field">
              Category
              <select className="input" value={values.category} onChange={set('category')}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {label(c)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Priority
              <select className="input" value={values.priority} onChange={set('priority')}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {label(p)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div className="field-row">
          <label className="field">
            Status
            <select className="input" value={values.status} onChange={set('status')}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {label(s)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Source
            <select className="input" value={values.source} onChange={set('source')}>
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {label(s)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field">
          Assigned to
          <input
            className="input"
            value={values.assigned_to}
            onChange={set('assigned_to')}
            placeholder="agent id or empty for unassigned"
          />
        </label>

        <label className="field">
          Tags <span className="muted">(comma-separated)</span>
          <input className="input" value={values.tags} onChange={set('tags')} />
        </label>

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Create ticket'}
          </button>
        </div>
      </form>
    </div>
  );
}
