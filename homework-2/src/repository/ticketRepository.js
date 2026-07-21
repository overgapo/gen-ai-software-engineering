const fs = require('fs');
const path = require('path');

const SAVE_DELAY_MS = 100;

class TicketRepository {
  constructor({ snapshotPath = null } = {}) {
    this.snapshotPath = snapshotPath;
    this.tickets = new Map();
    this._saveTimer = null;
  }

  load() {
    if (!this.snapshotPath || !fs.existsSync(this.snapshotPath)) return;
    const raw = JSON.parse(fs.readFileSync(this.snapshotPath, 'utf8'));
    for (const ticket of raw) this.tickets.set(ticket.id, ticket);
  }

  create(ticket) {
    this.tickets.set(ticket.id, ticket);
    this._scheduleSave();
    return ticket;
  }

  createMany(tickets) {
    for (const ticket of tickets) this.tickets.set(ticket.id, ticket);
    this._scheduleSave();
    return tickets;
  }

  getById(id) {
    return this.tickets.get(id) || null;
  }

  update(id, ticket) {
    this.tickets.set(id, ticket);
    this._scheduleSave();
    return ticket;
  }

  delete(id) {
    const existed = this.tickets.delete(id);
    if (existed) this._scheduleSave();
    return existed;
  }

  list(filters = {}) {
    let result = [...this.tickets.values()];
    for (const field of ['category', 'priority', 'status', 'assigned_to', 'customer_id']) {
      if (filters[field] !== undefined) {
        result = result.filter((t) => t[field] === filters[field]);
      }
    }
    if (filters.search) {
      const q = String(filters.search).toLowerCase();
      result = result.filter(
        (t) =>
          t.subject.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q)
      );
    }
    return result.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  count() {
    return this.tickets.size;
  }

  clear() {
    this.tickets.clear();
    this._scheduleSave();
  }

  // Debounced async snapshot: never blocks the request path.
  _scheduleSave() {
    if (!this.snapshotPath) return;
    clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => {
      this._saveTimer = null;
      this._save().catch((err) => {
        console.error(`snapshot write failed: ${err.message}`);
      });
    }, SAVE_DELAY_MS);
    this._saveTimer.unref();
  }

  async _save() {
    const tmpPath = `${this.snapshotPath}.tmp`;
    await fs.promises.mkdir(path.dirname(this.snapshotPath), { recursive: true });
    await fs.promises.writeFile(tmpPath, JSON.stringify([...this.tickets.values()]));
    await fs.promises.rename(tmpPath, this.snapshotPath);
  }

  async flush() {
    if (!this._saveTimer) return;
    clearTimeout(this._saveTimer);
    this._saveTimer = null;
    await this._save();
  }
}

const DEFAULT_SNAPSHOT_PATH = path.join(__dirname, '..', '..', 'data', 'tickets.json');

function createRepository({ snapshotPath } = {}) {
  const resolvedPath =
    snapshotPath !== undefined
      ? snapshotPath
      : process.env.NODE_ENV === 'test'
        ? null
        : DEFAULT_SNAPSHOT_PATH;
  const repository = new TicketRepository({ snapshotPath: resolvedPath });
  repository.load();
  return repository;
}

module.exports = { TicketRepository, createRepository };
