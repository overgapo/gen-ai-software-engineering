import { label } from '../constants';

const dateFmt = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export default function TicketList({ tickets, selectedId, onSelect }) {
  if (tickets.length === 0) {
    return <div className="empty">No tickets match the current filters.</div>;
  }
  return (
    <ul className="ticket-list">
      {tickets.map((t) => (
        <li key={t.id}>
          <button
            className={`ticket-card ${t.id === selectedId ? 'is-selected' : ''}`}
            onClick={() => onSelect(t.id)}
          >
            <div className="ticket-card-top">
              <span className="ticket-subject">{t.subject}</span>
              <span className={`badge badge-priority-${t.priority}`}>{label(t.priority)}</span>
            </div>
            <div className="ticket-card-bottom">
              <span className={`badge badge-status-${t.status}`}>{label(t.status)}</span>
              <span className="badge badge-category">{label(t.category)}</span>
              <span className="ticket-meta">
                {t.customer_name || t.customer_email} · {dateFmt.format(new Date(t.created_at))}
              </span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
