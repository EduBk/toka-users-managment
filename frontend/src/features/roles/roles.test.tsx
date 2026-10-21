import { screen, waitFor, within } from '@testing-library/react';

import { ApiError } from '@/services/apiClient';
import { authApi } from '@/services/authApi';
import { rolesApi } from '@/services/rolesApi';
import { usersApi } from '@/services/usersApi';
import { useRolesStore } from '@/stores/rolesStore';
import { useToastStore } from '@/stores/toastStore';
import { makeRole, makeUser, page } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { ADMIN, signIn } from '@/test/session';

jest.mock('@/services/rolesApi', () => ({
  rolesApi: {
    list: jest.fn(),
    create: jest.fn(),
    updatePermissions: jest.fn(),
    userRoles: jest.fn(),
    userPermissions: jest.fn(),
    assign: jest.fn(),
    revoke: jest.fn(),
  },
}));
jest.mock('@/services/authApi', () => ({
  authApi: { login: jest.fn(), refresh: jest.fn(), logout: jest.fn(), findAccount: jest.fn() },
}));
jest.mock('@/services/usersApi', () => ({
  usersApi: { list: jest.fn(), get: jest.fn() },
}));

const mockedRolesApi = jest.mocked(rolesApi);
const admin = makeRole();
const auditor = makeRole({
  id: '00000000-0000-4000-8000-000000000003',
  name: 'auditor',
  description: 'Auditor',
  permissions: ['audit:read'],
});
const ana = makeUser();
const account = {
  id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  email: ana.email,
  is_active: true,
  created_at: '2026-10-01T10:00:00Z',
};

beforeEach(() => {
  jest.resetAllMocks();
  useToastStore.setState({ toasts: [] });
  useRolesStore.setState({ roles: [], status: 'idle', mutationStatus: 'idle' });
  jest.mocked(usersApi.list).mockResolvedValue(page([ana]));
  jest.mocked(usersApi.get).mockResolvedValue(ana);
  mockedRolesApi.list.mockResolvedValue([admin, auditor]);
  signIn();
});

describe('vista de roles', () => {
  it('lista los roles con sus permisos', async () => {
    renderApp('/roles');

    const card = await screen.findByRole('article', { name: 'Rol auditor' });
    expect(within(card).getByText('audit')).toBeInTheDocument();
    expect(within(card).getByText(':read')).toBeInTheDocument();
  });

  it('crea un rol con los permisos elegidos', async () => {
    const support = makeRole({ id: 'r-support', name: 'support', permissions: ['users:read'] });
    mockedRolesApi.create.mockResolvedValue(support);
    const { user } = renderApp('/roles');
    await screen.findByRole('article', { name: 'Rol admin' });

    await user.click(screen.getByRole('button', { name: 'Nuevo rol' }));
    const form = screen.getByRole('form', { name: 'Nuevo rol' });
    await user.type(within(form).getByLabelText('Nombre'), 'Support');
    await user.click(within(form).getByLabelText('users:read'));
    await user.click(within(form).getByRole('button', { name: 'Crear rol' }));

    await waitFor(() =>
      expect(mockedRolesApi.create).toHaveBeenCalledWith({
        name: 'support',
        description: '',
        permissions: ['users:read'],
      }),
    );
    expect(await screen.findByRole('article', { name: 'Rol support' })).toBeInTheDocument();
  });

  it('valida el nombre del rol', async () => {
    const { user } = renderApp('/roles');
    await screen.findByRole('article', { name: 'Rol admin' });

    await user.click(screen.getByRole('button', { name: 'Nuevo rol' }));
    const form = screen.getByRole('form', { name: 'Nuevo rol' });
    await user.type(within(form).getByLabelText('Nombre'), 'con espacios');
    await user.click(within(form).getByRole('button', { name: 'Crear rol' }));

    expect(within(form).getByText(/letras minúsculas/)).toBeInTheDocument();
    expect(mockedRolesApi.create).not.toHaveBeenCalled();
  });

  it('reemplaza los permisos de un rol', async () => {
    mockedRolesApi.updatePermissions.mockResolvedValue({
      ...auditor,
      permissions: ['ai:use', 'audit:read'],
      updated_at: '2026-10-21T00:00:00Z',
    });
    const { user } = renderApp('/roles');
    const card = await screen.findByRole('article', { name: 'Rol auditor' });

    await user.click(within(card).getByRole('button', { name: 'Editar permisos' }));
    await user.click(within(card).getByLabelText('ai:use'));
    await user.click(within(card).getByRole('button', { name: 'Guardar permisos' }));

    await waitFor(() =>
      expect(mockedRolesApi.updatePermissions).toHaveBeenCalledWith(auditor.id, [
        'ai:use',
        'audit:read',
      ]),
    );
    expect(await screen.findByText('Permisos de auditor guardados.')).toBeInTheDocument();
  });

  it('deniega la vista a quien no es admin', async () => {
    signIn({ ...ADMIN, roles: ['auditor'], scopes: ['audit:read'] });
    renderApp('/roles');

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeInTheDocument();
    expect(mockedRolesApi.list).not.toHaveBeenCalled();
  });
});

describe('roles de un usuario', () => {
  beforeEach(() => {
    jest.mocked(authApi.findAccount).mockResolvedValue(account);
  });

  it('asigna un rol y muestra los permisos efectivos', async () => {
    mockedRolesApi.userRoles.mockResolvedValueOnce([]).mockResolvedValue([auditor]);
    mockedRolesApi.userPermissions
      .mockResolvedValueOnce({ user_id: account.id, permissions: [] })
      .mockResolvedValue({ user_id: account.id, permissions: ['audit:read'] });
    mockedRolesApi.assign.mockResolvedValue(undefined);
    const { user } = renderApp(`/users/${ana.id}`);

    const select = await screen.findByLabelText('Asignar rol');
    await waitFor(() =>
      expect(within(select).getByRole('option', { name: 'auditor' })).toBeInTheDocument(),
    );
    await user.selectOptions(select, auditor.id);
    await user.click(screen.getByRole('button', { name: 'Asignar' }));

    await waitFor(() => expect(mockedRolesApi.assign).toHaveBeenCalledWith(account.id, auditor.id));
    expect(authApi.findAccount).toHaveBeenCalledWith(ana.email);
    const effective = screen.getByRole('region', { name: 'Permisos efectivos' });
    expect(await within(effective).findByText('audit')).toBeInTheDocument();
    expect(screen.getByText('Rol auditor asignado.')).toBeInTheDocument();
  });

  it('revoca un rol tras confirmar', async () => {
    mockedRolesApi.userRoles.mockResolvedValueOnce([auditor]).mockResolvedValue([]);
    mockedRolesApi.userPermissions
      .mockResolvedValueOnce({ user_id: account.id, permissions: ['audit:read'] })
      .mockResolvedValue({ user_id: account.id, permissions: [] });
    mockedRolesApi.revoke.mockResolvedValue(undefined);
    const { user } = renderApp(`/users/${ana.id}`);

    await user.click(await screen.findByRole('button', { name: 'Revocar' }));
    await user.click(
      within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Revocar' }),
    );

    await waitFor(() => expect(mockedRolesApi.revoke).toHaveBeenCalledWith(account.id, auditor.id));
    expect(await screen.findByText('Sin roles asignados.')).toBeInTheDocument();
  });

  it('avisa si el usuario no tiene cuenta de acceso', async () => {
    jest
      .mocked(authApi.findAccount)
      .mockRejectedValue(new ApiError(404, { code: 'account_not_found', message: 'x' }));
    renderApp(`/users/${ana.id}`);

    expect(await screen.findByText(/todavía no tiene cuenta de acceso/)).toBeInTheDocument();
    expect(mockedRolesApi.userRoles).not.toHaveBeenCalled();
  });

  it('no muestra el panel de roles a quien no es admin', async () => {
    signIn({ ...ADMIN, roles: ['editor'], scopes: ['users:read'] });
    renderApp(`/users/${ana.id}`);

    expect(await screen.findByRole('heading', { name: 'Ana Pérez' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Roles y permisos' })).not.toBeInTheDocument();
    expect(authApi.findAccount).not.toHaveBeenCalled();
  });
});
