import { STATUSES, label } from '../constants';

const dateFmt = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

const fmt = (iso) => (iso ? dateFmt.format(new Date(iso)) : '—');

function Classification({ classification }) {
  if (!classification) {
    return <p className="muted">Not classified yet. Run auto-classify to get a suggestion.</p>;
  }
  const pct = Math.round(classification.confidence * 100);
  return (
    <dl className="detail-grid">
      <dt>Result</dt>
      <dd>
        {label(classification.category)} / {label(classification.priority)}
        {classification.overridden && <span className="badge badge-overridden">overridden</span>}
      </dd>
      <dt>Confidence</dt>
      <dd>
        <span className="confidence-bar" aria-label={`confidence ${pct}%`}>
          <span className="confidence-fill" style={{ width: `${pct}%` }} />
        </span>{' '}
        {pct}%
      </dd>
      <dt>Reasoning</dt>
      <dd>{classification.reasoning}</dd>
      <dt>Keywords</dt>
      <dd>
        {classification.keywords.length
          ? classification.keywords.map((k) => (
              <span key={k} className="badge badge-keyword">
                {k}
              </span>
            ))
          : '—'}
      </dd>
      <dt>Classified at</dt>
      <dd>{fmt(classification.classified_at)}</dd>
    </dl>
  );
}

export default function TicketDetail({
  ticket,
  onClose,
  onEdit,
  onDelete,
  onClassify,
  onStatusChange,
}) {
  return (
    <aside className="detail">
      <div className="detail-header">
        <h2>{ticket.subject}</h2>
        <button className="btn btn-small" onClick={onClose} aria-label="Close details">
          ✕
        </button>
      </div>

      <div className="detail-actions">
        <select
          className="input"
          value={ticket.status}
          aria-label="Change status"
          onChange={(e) => onStatusChange(e.target.value)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </select>
        <button className="btn" onClick={onClassify}>
          Auto-classify
        </button>
        <button className="btn" onClick={onEdit}>
          Edit
        </button>
        <button className="btn btn-danger" onClick={onDelete}>
          Delete
        </button>
      </div>

      <p className="detail-description">{ticket.description}</p>

      <h3>Details</h3>
      <dl className="detail-grid">
        <dt>Customer</dt>
        <dd>
          {ticket.customer_name || '—'} ({ticket.customer_email})
          {ticket.customer_id && <span className="muted"> · {ticket.customer_id}</span>}
        </dd>
        <dt>Category</dt>
        <dd>{label(ticket.category)}</dd>
        <dt>Priority</dt>
        <dd>
          <span className={`badge badge-priority-${ticket.priority}`}>{label(ticket.priority)}</span>
        </dd>
        <dt>Assigned to</dt>
        <dd>{ticket.assigned_to || 'Unassigned'}</dd>
        <dt>Tags</dt>
        <dd>
          {ticket.tags.length
            ? ticket.tags.map((t) => (
                <span key={t} className="badge badge-keyword">
                  {t}
                </span>
              ))
            : '—'}
        </dd>
        <dt>Source</dt>
        <dd>
          {label(ticket.metadata.source || 'api')}
          {ticket.metadata.device_type && ` · ${label(ticket.metadata.device_type)}`}
          {ticket.metadata.browser && ` · ${ticket.metadata.browser}`}
        </dd>
        <dt>Created</dt>
        <dd>{fmt(ticket.created_at)}</dd>
        <dt>Updated</dt>
        <dd>{fmt(ticket.updated_at)}</dd>
        <dt>Resolved</dt>
        <dd>{fmt(ticket.resolved_at)}</dd>
      </dl>

      <h3>Classification</h3>
      <Classification classification={ticket.classification} />
    </aside>
  );
}
