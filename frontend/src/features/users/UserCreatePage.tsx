import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/ui/card';
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
      <PageHeader
        title="Nuevo usuario"
        description="Crea una cuenta y define los datos con los que accederá al sistema."
      />
      <Card>
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
      </Card>
    </section>
  );
}
