import { screen, waitFor, within } from '@testing-library/react';

import { ApiError } from '@/services/apiClient';
import { usersApi } from '@/services/usersApi';
import { useToastStore } from '@/stores/toastStore';
import { makeUser, page } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { ADMIN, signIn } from '@/test/session';

jest.mock('@/services/usersApi', () => ({
  usersApi: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    deactivate: jest.fn(),
  },
}));

const mockedUsersApi = jest.mocked(usersApi);
const ana = makeUser();
const luis = makeUser({
  id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  email: 'luis@example.com',
  name: 'Luis Gómez',
  status: 'inactive',
});

const EDITOR = { ...ADMIN, roles: ['editor'], scopes: ['users:read', 'users:write'] };

beforeEach(() => {
  jest.resetAllMocks();
  useToastStore.setState({ toasts: [] });
  signIn(EDITOR);
});

describe('listado de usuarios', () => {
  it('muestra los usuarios de la página con su estado', async () => {
    mockedUsersApi.list.mockResolvedValue(page([ana, luis]));
    renderApp('/users');

    const table = await screen.findByRole('table');
    expect(within(table).getByText('Ana Pérez')).toBeInTheDocument();
    expect(within(table).getByText('Inactivo')).toBeInTheDocument();
    expect(mockedUsersApi.list).toHaveBeenCalledWith(1, 20);
  });

  it('filtra la página actual por nombre o email', async () => {
    mockedUsersApi.list.mockResolvedValue(page([ana, luis]));
    const { user } = renderApp('/users');
    await screen.findByRole('table');

    await user.type(screen.getByLabelText('Buscar en esta página'), 'luis@');

    expect(screen.queryByText('Ana Pérez')).not.toBeInTheDocument();
    expect(screen.getByText('Luis Gómez')).toBeInTheDocument();
  });

  it('pagina contra el backend', async () => {
    mockedUsersApi.list
      .mockResolvedValueOnce(page([ana], 25, 1, 20))
      .mockResolvedValueOnce(page([luis], 25, 2, 20));
    const { user } = renderApp('/users');
    await screen.findByText('Página 1 de 2 (25 usuarios)');

    await user.click(screen.getByRole('button', { name: 'Siguiente' }));

    expect(await screen.findByText('Luis Gómez')).toBeInTheDocument();
    expect(mockedUsersApi.list).toHaveBeenLastCalledWith(2, 20);
  });

  it('muestra el error del backend y permite reintentar', async () => {
    mockedUsersApi.list
      .mockRejectedValueOnce(new ApiError(503, { code: 'service_unavailable', message: 'down' }))
      .mockResolvedValueOnce(page([ana]));
    const { user } = renderApp('/users');

    expect(await screen.findByRole('alert')).toHaveTextContent('El servicio no está disponible');
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
  });

  it('muestra un estado vacío sin usuarios', async () => {
    mockedUsersApi.list.mockResolvedValue(page([]));
    renderApp('/users');

    expect(await screen.findByText('Todavía no hay usuarios')).toBeInTheDocument();
  });

  it('oculta la creación a quien solo puede leer', async () => {
    signIn({ ...ADMIN, roles: ['viewer'], scopes: ['users:read'] });
    mockedUsersApi.list.mockResolvedValue(page([ana]));
    renderApp('/users');

    await screen.findByRole('table');
    expect(screen.queryByRole('link', { name: 'Nuevo usuario' })).not.toBeInTheDocument();
  });
});

describe('alta de usuario', () => {
  it('valida email y nombre antes de llamar al API', async () => {
    const { user } = renderApp('/users/new');

    await user.type(await screen.findByLabelText('Email'), 'mal');
    await user.click(screen.getByRole('button', { name: 'Crear usuario' }));

    expect(screen.getByText('Introduce un nombre.')).toBeInTheDocument();
    expect(screen.getByText('Introduce un email válido.')).toBeInTheDocument();
    expect(mockedUsersApi.create).not.toHaveBeenCalled();
  });

  it('crea el usuario, avisa y navega a su detalle', async () => {
    mockedUsersApi.create.mockResolvedValue(ana);
    mockedUsersApi.get.mockResolvedValue(ana);
    mockedUsersApi.list.mockResolvedValue(page([ana]));
    const { router, user } = renderApp('/users/new');

    await user.type(await screen.findByLabelText('Nombre'), 'Ana Pérez');
    await user.type(screen.getByLabelText('Email'), 'ana@example.com');
    await user.click(screen.getByRole('button', { name: 'Crear usuario' }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/users/${ana.id}`));
    expect(mockedUsersApi.create).toHaveBeenCalledWith({
      name: 'Ana Pérez',
      email: 'ana@example.com',
    });
    expect(screen.getByText('Usuario Ana Pérez creado.')).toBeInTheDocument();
    expect(mockedUsersApi.list).toHaveBeenCalled();
  });

  it('muestra el conflicto de email sin romper el formulario', async () => {
    mockedUsersApi.create.mockRejectedValue(
      new ApiError(409, { code: 'email_already_exists', message: 'exists' }),
    );
    mockedUsersApi.list.mockResolvedValue(page([]));
    const { user } = renderApp('/users/new');

    await user.type(await screen.findByLabelText('Nombre'), 'Ana');
    await user.type(screen.getByLabelText('Email'), 'ana@example.com');
    await user.click(screen.getByRole('button', { name: 'Crear usuario' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ya existe un usuario con ese email.',
    );
    expect(screen.getByLabelText('Nombre')).toHaveValue('Ana');
  });
});

describe('detalle de usuario', () => {
  it('envía solo los campos modificados', async () => {
    mockedUsersApi.get.mockResolvedValue(ana);
    mockedUsersApi.update.mockResolvedValue({
      ...ana,
      name: 'Ana María',
      updated_at: '2026-10-02T00:00:00Z',
    });
    mockedUsersApi.list.mockResolvedValue(page([ana]));
    const { user } = renderApp(`/users/${ana.id}`);

    const name = await screen.findByLabelText('Nombre');
    await user.clear(name);
    await user.type(name, 'Ana María');
    await user.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() =>
      expect(mockedUsersApi.update).toHaveBeenCalledWith(ana.id, { name: 'Ana María' }),
    );
    expect(await screen.findByText('Cambios guardados.')).toBeInTheDocument();
  });

  it('pide confirmación antes de desactivar', async () => {
    mockedUsersApi.get.mockResolvedValue(ana);
    mockedUsersApi.deactivate.mockResolvedValue(undefined);
    mockedUsersApi.list.mockResolvedValue(page([ana]));
    const { user } = renderApp(`/users/${ana.id}`);

    await user.click(await screen.findByRole('button', { name: 'Desactivar usuario' }));
    const dialog = screen.getByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar' }));
    expect(mockedUsersApi.deactivate).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Desactivar usuario' }));
    await user.click(
      within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Desactivar' }),
    );

    await waitFor(() => expect(mockedUsersApi.deactivate).toHaveBeenCalledWith(ana.id));
    expect(await screen.findByText('Usuario Ana Pérez desactivado.')).toBeInTheDocument();
    expect(screen.getAllByText('Inactivo').length).toBeGreaterThan(0);
    expect(screen.getByLabelText('Nombre')).toBeDisabled();
  });

  it('muestra un error si el usuario no existe', async () => {
    mockedUsersApi.get.mockRejectedValue(
      new ApiError(404, { code: 'user_not_found', message: 'x' }),
    );
    renderApp(`/users/${ana.id}`);

    expect(await screen.findByRole('alert')).toHaveTextContent('El usuario no existe.');
  });
});
