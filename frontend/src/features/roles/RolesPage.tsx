import { useEffect, useMemo, useState } from 'react';

import { EmptyState, ErrorState, Skeleton } from '@/components/feedback';
import { PermissionChips, PermissionPicker } from '@/features/roles/PermissionControls';
import { permissionCatalog } from '@/features/roles/permissions';
import { RoleCreateForm } from '@/features/roles/RoleCreateForm';
import { useRolesStore } from '@/stores/rolesStore';
import { notify } from '@/stores/toastStore';
import type { Role } from '@/types/domain';

function RoleRow({ role, catalog }: { role: Role; catalog: string[] }) {
  const { updatePermissions, mutationStatus } = useRolesStore();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(role.permissions);
  const busy = mutationStatus === 'loading';

  async function save() {
    if (await updatePermissions(role.id, draft)) {
      notify.success(`Permisos de ${role.name} guardados.`);
      setEditing(false);
    } else {
      notify.error(
        useRolesStore.getState().mutationError ?? 'No se pudieron guardar los permisos.',
      );
    }
  }

  return (
    <article className="role" aria-label={`Rol ${role.name}`}>
      <div className="role__header">
        <div>
          <h2>{role.name}</h2>
          {role.description && <p className="muted">{role.description}</p>}
        </div>
        {!editing && (
          <button
            type="button"
            className="button button--secondary button--small"
            onClick={() => {
              setDraft(role.permissions);
              setEditing(true);
            }}
          >
            Editar permisos
          </button>
        )}
      </div>
      {editing ? (
        <div className="role__editor">
          <PermissionPicker catalog={catalog} value={draft} disabled={busy} onChange={setDraft} />
          <div className="form__actions">
            <button type="button" className="button" onClick={() => void save()} disabled={busy}>
              {busy ? 'Guardando…' : 'Guardar permisos'}
            </button>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => setEditing(false)}
              disabled={busy}
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <PermissionChips permissions={role.permissions} />
      )}
    </article>
  );
}

export function RolesPage() {
  const { roles, status, error, fetchRoles, createRole, mutationStatus, mutationError } =
    useRolesStore();
  const [creating, setCreating] = useState(false);
  const catalog = useMemo(() => permissionCatalog(roles), [roles]);

  useEffect(() => {
    void fetchRoles();
  }, [fetchRoles]);

  return (
    <section>
      <div className="page-header">
        <h1>Roles</h1>
        {!creating && (
          <button
            type="button"
            className="button"
            onClick={() => {
              useRolesStore.setState({ mutationStatus: 'idle', mutationError: null });
              setCreating(true);
            }}
          >
            Nuevo rol
          </button>
        )}
      </div>

      {creating && (
        <div className="panel role-create">
          <h2>Nuevo rol</h2>
          <RoleCreateForm
            catalog={catalog}
            busy={mutationStatus === 'loading'}
            error={mutationStatus === 'error' ? mutationError : null}
            onSubmit={async (input) => {
              const role = await createRole(input);
              if (role) {
                notify.success(`Rol ${role.name} creado.`);
                setCreating(false);
              }
            }}
            onCancel={() => setCreating(false)}
          />
        </div>
      )}

      {(status === 'idle' || status === 'loading') && <Skeleton rows={3} label="Cargando roles" />}
      {status === 'error' && (
        <ErrorState
          message={error ?? 'No se pudieron cargar los roles.'}
          onRetry={() => void fetchRoles()}
        />
      )}
      {status === 'success' && roles.length === 0 && (
        <EmptyState
          title="No hay roles"
          description="Crea un rol para empezar a asignar permisos."
        />
      )}
      {status === 'success' && roles.length > 0 && (
        <div className="roles">
          {roles.map((role) => (
            <RoleRow key={`${role.id}-${role.updated_at}`} role={role} catalog={catalog} />
          ))}
        </div>
      )}
    </section>
  );
}
