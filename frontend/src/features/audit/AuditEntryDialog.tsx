import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { AuditEntry } from '@/types/domain';

interface AuditEntryDialogProps {
  entry: AuditEntry;
  onClose: () => void;
}

const dateTimeFormat = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'medium' });

export function AuditEntryDialog({ entry, onClose }: AuditEntryDialogProps) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{entry.type}</DialogTitle>
          <DialogDescription>Detalle del evento y su payload.</DialogDescription>
        </DialogHeader>
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
        <h3 className="font-display text-sm font-semibold text-foreground">Payload</h3>
        <pre className="payload">{JSON.stringify(entry.payload, null, 2)}</pre>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
