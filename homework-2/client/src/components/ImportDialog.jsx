import { useState } from 'react';
import { api } from '../api';

export default function ImportDialog({ onClose, onImported }) {
  const [file, setFile] = useState(null);
  const [autoClassify, setAutoClassify] = useState(true);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleImport = async () => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    try {
      const summary = await api.import(file, autoClassify);
      setResult({ ok: true, summary });
      onImported(summary);
    } catch (err) {
      setResult({ ok: false, summary: err.body, message: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Import tickets</h2>
        <p className="muted">
          Upload a .csv, .json or .xml file. Import is all-or-nothing: if any record is
          invalid, nothing is imported.
        </p>

        <label className="field">
          File
          <input
            className="input"
            type="file"
            accept=".csv,.json,.xml"
            onChange={(e) => {
              setFile(e.target.files[0] ?? null);
              setResult(null);
            }}
          />
        </label>

        <label className="field field-inline">
          <input
            type="checkbox"
            checked={autoClassify}
            onChange={(e) => setAutoClassify(e.target.checked)}
          />
          Auto-classify imported tickets
        </label>

        {result && (
          <div className={`banner ${result.ok ? 'banner-success' : 'banner-error'}`}>
            {result.ok ? (
              <>Imported {result.summary.successful} of {result.summary.total} record(s).</>
            ) : (
              <>
                <strong>{result.message}</strong>
                {result.summary?.total !== undefined && (
                  <div>
                    {result.summary.failed} of {result.summary.total} record(s) invalid — nothing
                    was imported.
                  </div>
                )}
                {result.summary?.reason && <div>{result.summary.reason}</div>}
                {result.summary?.errors?.length > 0 && (
                  <ul className="import-errors">
                    {result.summary.errors.map((e) => (
                      <li key={e.record}>
                        Record {e.record}:{' '}
                        {e.details.map((d) => `${d.field} ${d.message}`).join('; ')}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>
            Close
          </button>
          <button className="btn btn-primary" disabled={!file || busy} onClick={handleImport}>
            {busy ? 'Importing…' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
