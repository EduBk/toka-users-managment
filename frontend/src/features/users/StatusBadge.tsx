import { Badge } from '@/components/ui/badge';
import type { UserStatus } from '@/types/domain';

export function StatusBadge({ status }: { status: UserStatus }) {
  return status === 'active' ? <Badge>Activo</Badge> : <Badge variant="secondary">Inactivo</Badge>;
}
