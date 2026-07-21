import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import FiltersBar from './components/FiltersBar';
import TicketList from './components/TicketList';
import TicketDetail from './components/TicketDetail';
import TicketForm from './components/TicketForm';
import ImportDialog from './components/ImportDialog';

const EMPTY_FILTERS = { category: '', priority: '', status: '', search: '' };

export default function App() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [tickets, setTickets] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  // undefined = form closed, null = create form, object = edit form
  const [formTicket, setFormTicket] = useState(undefined);
  const [importOpen, setImportOpen] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [toasts, setToasts] = useState([]);
  const toastSeq = useRef(0);

  const notify = useCallback((kind, text) => {
    const id = ++toastSeq.current;
    setToasts((prev) => [...prev, { id, kind, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setTickets(await api.list(filters));
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message);
    }
  }, [filters]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    api
      .get(selectedId)
      .then(setSelected)
      .catch((err) => {
        notify('error', err.message);
        setSelectedId(null);
      });
  }, [selectedId, notify]);

  const handleSave = async (payload, { autoClassify } = {}) => {
    if (formTicket) {
      const updated = await api.update(formTicket.id, payload);
      if (selectedId === updated.id) setSelected(updated);
      notify('success', 'Ticket updated');
    } else {
      const created = await api.create(payload, autoClassify);
      setSelectedId(created.id);
      notify('success', 'Ticket created');
    }
    setFormTicket(undefined);
    refresh();
  };

  const handleDelete = async (ticket) => {
    if (!window.confirm(`Delete ticket "${ticket.subject}"?`)) return;
    try {
      await api.remove(ticket.id);
      notify('success', 'Ticket deleted');
      if (selectedId === ticket.id) setSelectedId(null);
      refresh();
    } catch (err) {
      notify('error', err.message);
    }
  };

  const handleClassify = async (ticket) => {
    try {
      const updated = await api.classify(ticket.id);
      setSelected(updated);
      notify(
        'success',
        `Classified as ${updated.classification.category} / ${updated.classification.priority}`
      );
      refresh();
    } catch (err) {
      notify('error', err.message);
    }
  };

  const handleStatusChange = async (ticket, status) => {
    try {
      const updated = await api.update(ticket.id, { status });
      setSelected(updated);
      notify('success', `Status changed to ${status}`);
      refresh();
    } catch (err) {
      notify('error', err.message);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🎧 Support Tickets</h1>
        <div className="header-actions">
          <button className="btn" onClick={() => setImportOpen(true)}>
            Import
          </button>
          <button className="btn btn-primary" onClick={() => setFormTicket(null)}>
            New ticket
          </button>
        </div>
      </header>

      <FiltersBar filters={filters} onChange={setFilters} />

      {loadError ? (
        <div className="banner banner-error">
          Failed to load tickets: {loadError}{' '}
          <button className="btn btn-small" onClick={refresh}>
            Retry
          </button>
        </div>
      ) : (
        <main className="layout">
          <TicketList tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} />
          {selected && (
            <TicketDetail
              ticket={selected}
              onClose={() => setSelectedId(null)}
              onEdit={() => setFormTicket(selected)}
              onDelete={() => handleDelete(selected)}
              onClassify={() => handleClassify(selected)}
              onStatusChange={(status) => handleStatusChange(selected, status)}
            />
          )}
        </main>
      )}

      {formTicket !== undefined && (
        <TicketForm
          ticket={formTicket}
          onSave={handleSave}
          onCancel={() => setFormTicket(undefined)}
        />
      )}

      {importOpen && (
        <ImportDialog
          onClose={() => setImportOpen(false)}
          onImported={(summary) => {
            notify('success', `Imported ${summary.successful} ticket(s)`);
            refresh();
          }}
        />
      )}

      <div className="toasts" role="status">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
