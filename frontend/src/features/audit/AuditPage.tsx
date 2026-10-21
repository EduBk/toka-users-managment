import { useCallback, useEffect, useState } from 'react';

import { EmptyState, ErrorState, Skeleton } from '@/components/feedback';
import { AuditEntryDialog } from '@/features/audit/AuditEntryDialog';
import { AuditFiltersForm } from '@/features/audit/AuditFiltersForm';
import { useAuditStore } from '@/stores/auditStore';
import type { AuditEntry } from '@/types/domain';

const dateTimeFormat = new Intl.DateTimeFormat('es', { dateStyle: 'short', timeStyle: 'medium' });

export function AuditPage() {
  const { items, total, page, pageSize, status, error, fetchPage, applyFilters } = useAuditStore();
  const [detail, setDetail] = useState<AuditEntry | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const closeDetail = useCallback(() => setDetail(null), []);

  useEffect(() => {
    void fetchPage(1);
  }, [fetchPage]);

  return (
    <section>
      <div className="page-header">
        <h1>Auditoría</h1>
      </div>

      <AuditFiltersForm
        busy={status === 'loading'}
        onApply={(filters) => void applyFilters(filters)}
      />

      {(status === 'idle' || status === 'loading') && <Skeleton label="Cargando eventos" />}
      {status === 'error' && (
        <ErrorState
          message={error ?? 'No se pudieron cargar los eventos.'}
          onRetry={() => void fetchPage()}
        />
      )}
      {status === 'success' && items.length === 0 && (
        <EmptyState
          title="Sin eventos"
          description="No hay eventos que coincidan con los filtros."
        />
      )}
      {status === 'success' && items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Fecha</th>
                <th scope="col">Tipo</th>
                <th scope="col">Productor</th>
                <th scope="col">Actor</th>
                <th scope="col">
                  <span className="visually-hidden">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => (
                <tr key={entry.event_id}>
                  <td>{dateTimeFormat.format(new Date(entry.occurred_at))}</td>
                  <td>
                    <code>{entry.type}</code>
                  </td>
                  <td>{entry.producer}</td>
                  <td className="muted">{entry.actor_id ?? '—'}</td>
                  <td className="table__actions">
                    <button
                      type="button"
                      className="button button--secondary button--small"
                      aria-label={`Ver detalle de ${entry.type}`}
                      onClick={() => setDetail(entry)}
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {status === 'success' && total > 0 && (
        <nav className="pagination" aria-label="Paginación">
          <span>
            Página {page} de {totalPages} ({total} eventos)
          </span>
          <div className="pagination__buttons">
            <button
              type="button"
              className="button button--secondary button--small"
              onClick={() => void fetchPage(page - 1)}
              disabled={page <= 1}
            >
              Anterior
            </button>
            <button
              type="button"
              className="button button--secondary button--small"
              onClick={() => void fetchPage(page + 1)}
              disabled={page >= totalPages}
            >
              Siguiente
            </button>
          </div>
        </nav>
      )}

      {detail && <AuditEntryDialog entry={detail} onClose={closeDetail} />}
    </section>
  );
}
