import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { EmptyState, ErrorState, Skeleton } from '@/components/feedback';
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
      <div className="page-header">
        <h1>Usuarios</h1>
        {canWrite && (
          <Link className="button" to="/users/new">
            Nuevo usuario
          </Link>
        )}
      </div>

      <div className="toolbar">
        <label className="field">
          <span className="field__label">Buscar en esta página</span>
          <input
            className="input"
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
              <Link className="button" to="/users/new">
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
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Email</th>
                <th scope="col">Estado</th>
                <th scope="col">Alta</th>
                <th scope="col">
                  <span className="visually-hidden">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((user) => (
                <tr key={user.id}>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>
                    <StatusBadge status={user.status} />
                  </td>
                  <td>{dateFormat.format(new Date(user.created_at))}</td>
                  <td className="table__actions">
                    <Link to={`/users/${user.id}`} aria-label={`Ver ${user.name}`}>
                      Ver detalle
                    </Link>
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
            Página {page} de {totalPages} ({total} usuarios)
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
    </section>
  );
}
