const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  TicketRepository,
  createRepository,
} = require('../src/repository/ticketRepository');

const ticket = (id) => ({
  id,
  subject: `subject ${id}`,
  description: `description ${id}`,
  created_at: new Date().toISOString(),
});

describe('repository snapshot persistence', () => {
  let dir;
  let snapshotPath;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ticket-snap-'));
    snapshotPath = path.join(dir, 'data', 'tickets.json');
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('persists mutations and restores them in a fresh repository', async () => {
    const repo = createRepository({ snapshotPath });
    repo.create(ticket('t-1'));
    repo.createMany([ticket('t-2'), ticket('t-3')]);
    repo.update('t-2', { ...ticket('t-2'), subject: 'updated' });
    repo.delete('t-3');
    await repo.flush();

    const restored = createRepository({ snapshotPath });
    expect(restored.count()).toBe(2);
    expect(restored.getById('t-2').subject).toBe('updated');
    expect(restored.getById('t-3')).toBeNull();
  });

  it('debounces the disk write instead of writing synchronously', async () => {
    const repo = new TicketRepository({ snapshotPath });
    repo.create(ticket('t-1'));
    expect(fs.existsSync(snapshotPath)).toBe(false);
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(fs.existsSync(snapshotPath)).toBe(true);
  });

  it('writes nothing when snapshotting is disabled', async () => {
    const repo = new TicketRepository();
    repo.create(ticket('t-1'));
    await repo.flush();
    expect(repo.snapshotPath).toBeNull();
    expect(fs.readdirSync(dir)).toEqual([]);
  });

  it('defaults to a disabled snapshot under NODE_ENV=test', () => {
    expect(createRepository().snapshotPath).toBeNull();
  });

  it('clear() empties the store and persists the empty state', async () => {
    const repo = new TicketRepository({ snapshotPath });
    repo.create(ticket('t-1'));
    repo.clear();
    await repo.flush();
    expect(JSON.parse(fs.readFileSync(snapshotPath, 'utf8'))).toEqual([]);
  });
});
