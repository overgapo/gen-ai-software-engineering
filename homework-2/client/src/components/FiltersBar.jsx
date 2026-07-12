import { CATEGORIES, PRIORITIES, STATUSES, label } from '../constants';

function Select({ name, value, options, onChange }) {
  return (
    <select
      className="input"
      aria-label={name}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">All {name}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {label(o)}
        </option>
      ))}
    </select>
  );
}

export default function FiltersBar({ filters, onChange }) {
  const set = (field) => (value) => onChange({ ...filters, [field]: value });
  return (
    <div className="filters">
      <input
        className="input filters-search"
        type="search"
        placeholder="Search subject or description…"
        value={filters.search}
        onChange={(e) => set('search')(e.target.value)}
      />
      <Select name="categories" value={filters.category} options={CATEGORIES} onChange={set('category')} />
      <Select name="priorities" value={filters.priority} options={PRIORITIES} onChange={set('priority')} />
      <Select name="statuses" value={filters.status} options={STATUSES} onChange={set('status')} />
    </div>
  );
}
