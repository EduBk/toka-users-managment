import { useEffect, useState } from 'react';

import { ConfirmDialog } from '@/components/ConfirmDialog';
import { ErrorState, Skeleton } from '@/components/feedback';
import { PermissionChips } from '@/features/roles/PermissionControls';
import { useRolesStore } from '@/stores/rolesStore';
import { notify } from '@/stores/toastStore';
import type { Role } from '@/types/domain';

export function UserRolesPanel({ email }: { email: string }) {
  const {
    roles,
    status: rolesStatus,
    fetchRoles,
    accountRoles,
    accountPermissions,
    accessStatus,
    accessError,
    loadAccountAccess,
    assignRole,
    revokeRole,
    mutationStatus,
  } = useRolesStore();
  const [roleToAssign, setRoleToAssign] = useState('');
  const [roleToRevoke, setRoleToRevoke] = useState<Role | null>(null);
  const busy = mutationStatus === 'loading';

  useEffect(() => {
    void loadAccountAccess(email);
  }, [email, loadAccountAccess]);

  useEffect(() => {
    if (rolesStatus === 'idle') void fetchRoles();
  }, [rolesStatus, fetchRoles]);

  const assignedIds = new Set(accountRoles.map((role) => role.id));
  const assignable = roles.filter((role) => !assignedIds.has(role.id));

  async function handleAssign() {
    const role = roles.find((item) => item.id === roleToAssign);
    if (!role) return;
    if (await assignRole(role.id)) {
      notify.success(`Rol ${role.name} asignado.`);
      setRoleToAssign('');
    } else {
      notify.error(useRolesStore.getState().mutationError ?? 'No se pudo asignar el rol.');
    }
  }

  async function handleRevoke() {
    if (!roleToRevoke) return;
    if (await revokeRole(roleToRevoke.id)) {
      notify.success(`Rol ${roleToRevoke.name} revocado.`);
    } else {
      notify.error(useRolesStore.getState().mutationError ?? 'No se pudo revocar el rol.');
    }
    setRoleToRevoke(null);
  }

  return (
    <div className="panel">
      <h2>Roles y permisos</h2>
      {(accessStatus === 'idle' || accessStatus === 'loading') && (
        <Skeleton rows={2} label="Cargando roles del usuario" />
      )}
      {accessStatus === 'error' && (
        <ErrorState
          message={accessError ?? 'No se pudieron cargar los roles del usuario.'}
          onRetry={() => void loadAccountAccess(email)}
        />
      )}
      {accessStatus === 'no-account' && (
        <p className="alert alert--info">
          Este usuario todavía no tiene cuenta de acceso con el email {email}. Podrá recibir roles
          cuando se registre.
        </p>
      )}
      {accessStatus === 'success' && (
        <div className="user-roles">
          <section aria-label="Roles asignados">
            <h3>Roles asignados</h3>
            {accountRoles.length === 0 ? (
              <p className="muted">Sin roles asignados.</p>
            ) : (
              <ul className="assigned-roles">
                {accountRoles.map((role) => (
                  <li key={role.id}>
                    <span className="assigned-roles__name">{role.name}</span>
                    <button
                      type="button"
                      className="button button--secondary button--small"
                      onClick={() => setRoleToRevoke(role)}
                      disabled={busy}
                    >
                      Revocar
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="toolbar">
              <label className="field">
                <span className="field__label">Asignar rol</span>
                <select
                  className="input"
                  value={roleToAssign}
                  onChange={(event) => setRoleToAssign(event.target.value)}
                  disabled={busy || assignable.length === 0}
                >
                  <option value="">
                    {assignable.length === 0 ? 'No quedan roles por asignar' : 'Elige un rol'}
                  </option>
                  {assignable.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="button"
                onClick={() => void handleAssign()}
                disabled={busy || !roleToAssign}
              >
                Asignar
              </button>
            </div>
          </section>
          <section aria-label="Permisos efectivos">
            <h3>Permisos efectivos</h3>
            <PermissionChips permissions={accountPermissions} />
            <p className="muted">
              Los cambios se aplican cuando el usuario vuelve a iniciar sesión o renueva su sesión.
            </p>
          </section>
        </div>
      )}

      {roleToRevoke && (
        <ConfirmDialog
          title={`¿Revocar el rol ${roleToRevoke.name}?`}
          message="El usuario perderá los permisos de este rol en su próxima sesión."
          confirmLabel="Revocar"
          busy={busy}
          onConfirm={() => void handleRevoke()}
          onCancel={() => setRoleToRevoke(null)}
        />
      )}
    </div>
  );
}
