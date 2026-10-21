import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { UserForm } from '@/features/users/UserForm';
import { notify } from '@/stores/toastStore';
import { useUsersStore } from '@/stores/usersStore';

export function UserCreatePage() {
  const navigate = useNavigate();
  const { createUser, mutationStatus, mutationError } = useUsersStore();

  useEffect(() => {
    useUsersStore.setState({ mutationStatus: 'idle', mutationError: null });
  }, []);

  return (
    <section>
      <div className="page-header">
        <h1>Nuevo usuario</h1>
      </div>
      <div className="panel">
        <UserForm
          submitLabel="Crear usuario"
          busy={mutationStatus === 'loading'}
          error={mutationStatus === 'error' ? mutationError : null}
          onSubmit={async (input) => {
            const user = await createUser(input);
            if (user) {
              notify.success(`Usuario ${user.name} creado.`);
              navigate(`/users/${user.id}`);
            }
          }}
          onCancel={() => navigate('/users')}
        />
      </div>
    </section>
  );
}
