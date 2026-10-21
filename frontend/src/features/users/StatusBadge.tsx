import type { UserStatus } from '@/types/domain';

export function StatusBadge({ status }: { status: UserStatus }) {
  return status === 'active' ? (
    <span className="badge">Activo</span>
  ) : (
    <span className="badge badge--inactive">Inactivo</span>
  );
}
