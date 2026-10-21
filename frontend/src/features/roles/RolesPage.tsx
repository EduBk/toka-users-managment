import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState, Skeleton } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
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
    <Card asChild>
      <article className="role" aria-label={`Rol ${role.name}`}>
        <div className="role__header">
          <div>
            <h2>{role.name}</h2>
            {role.description && <p className="muted">{role.description}</p>}
          </div>
          {!editing && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setDraft(role.permissions);
                setEditing(true);
              }}
            >
              Editar permisos
            </Button>
          )}
        </div>
        {editing ? (
          <div className="role__editor">
            <PermissionPicker catalog={catalog} value={draft} disabled={busy} onChange={setDraft} />
            <div className="form__actions">
              <Button type="button" onClick={() => void save()} disabled={busy}>
                {busy ? 'Guardando…' : 'Guardar permisos'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditing(false)}
                disabled={busy}
              >
                Cancelar
              </Button>
            </div>
          </div>
        ) : (
          <PermissionChips permissions={role.permissions} />
        )}
      </article>
    </Card>
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
      <PageHeader
        title="Roles"
        description="Define qué puede hacer cada rol y ajusta sus permisos por recurso."
        actions={
          !creating && (
            <Button
              type="button"
              onClick={() => {
                useRolesStore.setState({ mutationStatus: 'idle', mutationError: null });
                setCreating(true);
              }}
            >
              Nuevo rol
            </Button>
          )
        }
      />

      {creating && (
        <Card className="role-create">
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
        </Card>
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
