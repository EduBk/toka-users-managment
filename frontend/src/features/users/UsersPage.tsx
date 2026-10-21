import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, Skeleton } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { buttonVariants } from '@/components/ui/button-variants';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ACCESS, hasAccess } from '@/features/auth/access';
import { StatusBadge } from '@/features/users/StatusBadge';
import { useAuthStore } from '@/stores/authStore';
import { useUsersStore } from '@/stores/usersStore';

const dateFormat = new Intl.DateTimeFormat('es', { dateStyle: 'medium' });

export function UsersPage() {
  const { items, total, page, pageSize, status, error, fetchPage } = useUsersStore();
  const canWrite = hasAccess(
    useAuthStore((state) => state.user),
    ACCESS.usersWrite,
  );
  const [filter, setFilter] = useState('');
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    void fetchPage(1);
  }, [fetchPage]);

  const visible = useMemo(() => {
    const term = filter.trim().toLowerCase();
    if (!term) return items;
    return items.filter(
      (user) => user.name.toLowerCase().includes(term) || user.email.toLowerCase().includes(term),
    );
  }, [items, filter]);

  return (
    <section>
      <PageHeader
        title="Usuarios"
        description="Consulta las cuentas registradas, su estado y cuándo se dieron de alta."
        actions={
          canWrite && (
            <Link className={buttonVariants()} to="/users/new">
              Nuevo usuario
            </Link>
          )
        }
      />

      <div className="toolbar">
        <label className="field">
          <span className="field__label">Buscar en esta página</span>
          <Input
            type="search"
            placeholder="Nombre o email"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </label>
      </div>

      {(status === 'idle' || status === 'loading') && <Skeleton label="Cargando usuarios" />}
      {status === 'error' && (
        <ErrorState
          message={error ?? 'No se pudieron cargar los usuarios.'}
          onRetry={() => void fetchPage()}
        />
      )}
      {status === 'success' && items.length === 0 && (
        <EmptyState
          title="Todavía no hay usuarios"
          description="Los usuarios que crees aparecerán aquí."
          action={
            canWrite && (
              <Link className={buttonVariants()} to="/users/new">
                Crear el primer usuario
              </Link>
            )
          }
        />
      )}
      {status === 'success' && items.length > 0 && visible.length === 0 && (
        <EmptyState
          title="Sin coincidencias"
          description={`Ningún usuario de esta página coincide con «${filter.trim()}».`}
        />
      )}
      {status === 'success' && visible.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-secondary/60 hover:bg-secondary/60">
                <TableHead scope="col">Nombre</TableHead>
                <TableHead scope="col">Email</TableHead>
                <TableHead scope="col">Estado</TableHead>
                <TableHead scope="col">Alta</TableHead>
                <TableHead scope="col" className="text-right">
                  <span className="visually-hidden">Acciones</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium text-foreground">{user.name}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <StatusBadge status={user.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {dateFormat.format(new Date(user.created_at))}
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      className="text-sm font-semibold"
                      to={`/users/${user.id}`}
                      aria-label={`Ver ${user.name}`}
                    >
                      Ver detalle
                    </Link>
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
            Página {page} de {totalPages} ({total} usuarios)
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
    </section>
  );
}
