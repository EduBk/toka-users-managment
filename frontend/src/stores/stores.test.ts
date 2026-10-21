import { ApiError } from '@/services/apiClient';
import { authApi } from '@/services/authApi';
import { rolesApi } from '@/services/rolesApi';
import { usersApi } from '@/services/usersApi';
import { useRolesStore } from '@/stores/rolesStore';
import { useUsersStore } from '@/stores/usersStore';
import { makeRole, makeUser, page } from '@/test/fixtures';
import type { Page } from '@/types/api';
import type { User } from '@/types/domain';

jest.mock('@/services/usersApi', () => ({
  usersApi: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    deactivate: jest.fn(),
  },
}));
jest.mock('@/services/rolesApi', () => ({
  rolesApi: {
    list: jest.fn(),
    create: jest.fn(),
    userRoles: jest.fn(),
    userPermissions: jest.fn(),
    assign: jest.fn(),
  },
}));
jest.mock('@/services/authApi', () => ({ authApi: { findAccount: jest.fn() } }));

const unavailable = new ApiError(503, { code: 'service_unavailable', message: 'down' });

beforeEach(() => jest.resetAllMocks());

describe('usersStore', () => {
  it('pasa por loading y termina en success con la página', async () => {
    let resolve: (value: Page<User>) => void = () => {};
    jest.mocked(usersApi.list).mockReturnValue(new Promise((r) => (resolve = r)));

    const pending = useUsersStore.getState().fetchPage(1);
    expect(useUsersStore.getState().status).toBe('loading');

    resolve(page([makeUser()], 1));
    await pending;
    expect(useUsersStore.getState()).toMatchObject({ status: 'success', total: 1, error: null });
  });

  it('termina en error con un mensaje legible', async () => {
    jest.mocked(usersApi.list).mockRejectedValue(unavailable);

    await useUsersStore.getState().fetchPage(1);

    expect(useUsersStore.getState()).toMatchObject({
      status: 'error',
      error: 'El servicio no está disponible. Inténtalo de nuevo más tarde.',
    });
  });

  it('registra el error de una mutación sin tocar el listado', async () => {
    jest
      .mocked(usersApi.create)
      .mockRejectedValue(new ApiError(409, { code: 'email_already_exists', message: 'x' }));

    const result = await useUsersStore.getState().createUser({ email: 'a@b.co', name: 'A' });

    expect(result).toBeNull();
    expect(useUsersStore.getState()).toMatchObject({
      mutationStatus: 'error',
      mutationError: 'Ya existe un usuario con ese email.',
    });
    expect(usersApi.list).not.toHaveBeenCalled();
  });
});

describe('rolesStore', () => {
  it('carga los roles y marca success', async () => {
    jest.mocked(rolesApi.list).mockResolvedValue([makeRole()]);

    await useRolesStore.getState().fetchRoles();

    expect(useRolesStore.getState()).toMatchObject({ status: 'success', error: null });
    expect(useRolesStore.getState().roles).toHaveLength(1);
  });

  it('distingue la falta de cuenta de un error', async () => {
    jest
      .mocked(authApi.findAccount)
      .mockRejectedValueOnce(new ApiError(404, { code: 'account_not_found', message: 'x' }))
      .mockRejectedValueOnce(unavailable);

    await useRolesStore.getState().loadAccountAccess('a@b.co');
    expect(useRolesStore.getState().accessStatus).toBe('no-account');

    await useRolesStore.getState().loadAccountAccess('a@b.co');
    expect(useRolesStore.getState()).toMatchObject({
      accessStatus: 'error',
      accessError: 'El servicio no está disponible. Inténtalo de nuevo más tarde.',
    });
  });

  it('no asigna roles sin una cuenta cargada', async () => {
    useRolesStore.setState({ account: null });

    await expect(useRolesStore.getState().assignRole('r1')).resolves.toBe(false);
    expect(rolesApi.assign).not.toHaveBeenCalled();
  });
});
