import { useCallback, useEffect, useState } from 'react';

import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, Skeleton } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
      <PageHeader
        title="Auditoría"
        description="Revisa cada evento registrado: quién actuó, cuándo y sobre qué."
      />

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
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-secondary/60 hover:bg-secondary/60">
                <TableHead scope="col">Fecha</TableHead>
                <TableHead scope="col">Tipo</TableHead>
                <TableHead scope="col">Productor</TableHead>
                <TableHead scope="col">Actor</TableHead>
                <TableHead scope="col" className="text-right">
                  <span className="visually-hidden">Acciones</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((entry) => (
                <TableRow key={entry.event_id}>
                  <TableCell className="text-muted-foreground">
                    {dateTimeFormat.format(new Date(entry.occurred_at))}
                  </TableCell>
                  <TableCell>
                    <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs text-foreground">
                      {entry.type}
                    </code>
                  </TableCell>
                  <TableCell>{entry.producer}</TableCell>
                  <TableCell className="text-muted-foreground">{entry.actor_id ?? '—'}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Ver detalle de ${entry.type}`}
                      onClick={() => setDetail(entry)}
                    >
                      Ver detalle
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {status === 'success' && total > 0 && (
        <nav className="pagination" aria-label="Paginación">
          <span>
            Página {page} de {totalPages} ({total} eventos)
          </span>
          <div className="pagination__buttons">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void fetchPage(page - 1)}
              disabled={page <= 1}
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void fetchPage(page + 1)}
              disabled={page >= totalPages}
            >
              Siguiente
            </Button>
          </div>
        </nav>
      )}

      {detail && <AuditEntryDialog entry={detail} onClose={closeDetail} />}
    </section>
  );
}
