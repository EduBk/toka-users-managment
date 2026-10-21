import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ConfirmDialog } from '@/components/ConfirmDialog';
import { PageHeader } from '@/components/PageHeader';
import { ErrorState, Skeleton } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ACCESS, hasAccess } from '@/features/auth/access';
import { UserRolesPanel } from '@/features/roles/UserRolesPanel';
import { StatusBadge } from '@/features/users/StatusBadge';
import { UserForm } from '@/features/users/UserForm';
import { useAuthStore } from '@/stores/authStore';
import { notify } from '@/stores/toastStore';
import { useUsersStore } from '@/stores/usersStore';

export function UserDetailPage() {
  const { userId = '' } = useParams();
  const navigate = useNavigate();
  const sessionUser = useAuthStore((state) => state.user);
  const canWrite = hasAccess(sessionUser, ACCESS.usersWrite);
  const canManageRoles = hasAccess(sessionUser, ACCESS.rolesAdmin);
  const {
    selected,
    selectedStatus,
    selectedError,
    mutationStatus,
    mutationError,
    fetchUser,
    updateUser,
    deactivateUser,
  } = useUsersStore();
  const [confirming, setConfirming] = useState(false);
  const busy = mutationStatus === 'loading';

  useEffect(() => {
    useUsersStore.setState({ mutationStatus: 'idle', mutationError: null });
    void fetchUser(userId);
  }, [fetchUser, userId]);

  if (selectedStatus === 'error') {
    return (
      <ErrorState
        message={selectedError ?? 'No se pudo cargar el usuario.'}
        onRetry={() => void fetchUser(userId)}
      />
    );
  }
  if (!selected || selected.id !== userId) {
    return <Skeleton rows={3} label="Cargando usuario" />;
  }

  const inactive = selected.status === 'inactive';

  async function handleDeactivate() {
    if (await deactivateUser(userId)) {
      notify.success(`Usuario ${selected?.name} desactivado.`);
    } else {
      notify.error(useUsersStore.getState().mutationError ?? 'No se pudo desactivar el usuario.');
    }
    setConfirming(false);
  }

  return (
    <section>
      <PageHeader
        title={selected.name}
        description="Revisa y actualiza los datos de la cuenta, sus roles y permisos."
        breadcrumb={<Link to="/users">Usuarios</Link>}
        actions={<StatusBadge status={selected.status} />}
      />

      <div className="stack">
        <Card>
          <h2>Datos</h2>
          {inactive && (
            <p className="alert alert--info">
              El usuario está desactivado: sus datos ya no se pueden modificar.
            </p>
          )}
          <UserForm
            key={selected.updated_at}
            initial={{ email: selected.email, name: selected.name }}
            submitLabel="Guardar cambios"
            busy={busy}
            disabled={!canWrite || inactive}
            error={mutationStatus === 'error' && !confirming ? mutationError : null}
            onSubmit={async (input) => {
              const changes = {
                ...(input.email !== selected.email && { email: input.email }),
                ...(input.name !== selected.name && { name: input.name }),
              };
              if (Object.keys(changes).length === 0) {
                notify.success('No hay cambios que guardar.');
                return;
              }
              if (await updateUser(userId, changes)) notify.success('Cambios guardados.');
            }}
            onCancel={() => navigate('/users')}
          />
          {canWrite && !inactive && (
            <div className="danger-zone">
              <Button
                variant="destructive"
                type="button"
                onClick={() => setConfirming(true)}
                disabled={busy}
              >
                Desactivar usuario
              </Button>
            </div>
          )}
        </Card>

        {canManageRoles && <UserRolesPanel email={selected.email} />}
      </div>

      {confirming && (
        <ConfirmDialog
          title="¿Desactivar este usuario?"
          message={`${selected.name} quedará inactivo y no podrá editarse. Esta acción no se puede deshacer desde la aplicación.`}
          confirmLabel="Desactivar"
          busy={busy}
          onConfirm={() => void handleDeactivate()}
          onCancel={() => setConfirming(false)}
        />
      )}
    </section>
  );
}
