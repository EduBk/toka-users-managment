import { useState, type FormEvent } from 'react';

import { EVENT_TYPES } from '@/features/audit/eventTypes';
import type { AuditFilters } from '@/services/auditApi';

interface AuditFiltersFormProps {
  busy: boolean;
  onApply: (filters: AuditFilters) => void;
}

const EMPTY = { user: '', type: '', from: '', to: '' };

function startOfDay(date: string): string {
  return new Date(`${date}T00:00:00`).toISOString();
}

function endOfDay(date: string): string {
  return new Date(`${date}T23:59:59.999`).toISOString();
}

export function AuditFiltersForm({ busy, onApply }: AuditFiltersFormProps) {
  const [values, setValues] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  function update(field: keyof typeof EMPTY, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (values.from && values.to && values.from > values.to) {
      setError('La fecha «Desde» no puede ser posterior a «Hasta».');
      return;
    }
    setError(null);
    onApply({
      user: values.user.trim() || undefined,
      type: values.type || undefined,
      from: values.from ? startOfDay(values.from) : undefined,
      to: values.to ? endOfDay(values.to) : undefined,
    });
  }

  function handleReset() {
    setValues(EMPTY);
    setError(null);
    onApply({});
  }

  return (
    <form className="toolbar audit-filters" aria-label="Filtros" onSubmit={handleSubmit} noValidate>
      <label className="field">
        <span className="field__label">Usuario (ID)</span>
        <input
          className="input"
          value={values.user}
          maxLength={254}
          placeholder="ID de usuario o cuenta"
          onChange={(event) => update('user', event.target.value)}
        />
      </label>
      <label className="field">
        <span className="field__label">Tipo de evento</span>
        <select
          className="input"
          value={values.type}
          onChange={(event) => update('type', event.target.value)}
        >
          <option value="">Todos</option>
          {EVENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field__label">Desde</span>
        <input
          className="input"
          type="date"
          value={values.from}
          onChange={(event) => update('from', event.target.value)}
        />
      </label>
      <label className="field">
        <span className="field__label">Hasta</span>
        <input
          className="input"
          type="date"
          value={values.to}
          onChange={(event) => update('to', event.target.value)}
        />
      </label>
      <div className="audit-filters__actions">
        <button type="submit" className="button" disabled={busy}>
          Aplicar filtros
        </button>
        <button
          type="button"
          className="button button--secondary"
          onClick={handleReset}
          disabled={busy}
        >
          Limpiar
        </button>
      </div>
      {error && (
        <p className="alert audit-filters__error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
