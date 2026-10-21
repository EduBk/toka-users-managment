import { useEffect, useId, useRef } from 'react';

import type { AuditEntry } from '@/types/domain';

interface AuditEntryDialogProps {
  entry: AuditEntry;
  onClose: () => void;
}

const dateTimeFormat = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'medium' });

export function AuditEntryDialog({ entry, onClose }: AuditEntryDialogProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="dialog-backdrop">
      <div
        className="dialog dialog--wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <h2 id={titleId}>{entry.type}</h2>
        <dl className="details">
          <dt>Fecha</dt>
          <dd>{dateTimeFormat.format(new Date(entry.occurred_at))}</dd>
          <dt>Productor</dt>
          <dd>{entry.producer}</dd>
          <dt>Actor</dt>
          <dd>{entry.actor_id ?? '—'}</dd>
          <dt>Correlation ID</dt>
          <dd>
            <code>{entry.correlation_id}</code>
          </dd>
          <dt>Evento</dt>
          <dd>
            <code>{entry.event_id}</code> (v{entry.version})
          </dd>
        </dl>
        <h3>Payload</h3>
        <pre className="payload">{JSON.stringify(entry.payload, null, 2)}</pre>
        <div className="dialog__actions">
          <button
            ref={closeRef}
            type="button"
            className="button button--secondary"
            onClick={onClose}
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
