import { screen, waitFor } from '@testing-library/react';

import { ApiError } from '@/services/apiClient';
import { authApi } from '@/services/authApi';
import { usersApi } from '@/services/usersApi';
import { useAuthStore } from '@/stores/authStore';
import { page } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { ADMIN, makeAccessToken, signIn, signOut } from '@/test/session';

jest.mock('@/services/authApi', () => ({
  authApi: { login: jest.fn(), refresh: jest.fn(), logout: jest.fn() },
}));
jest.mock('@/services/usersApi', () => ({ usersApi: { list: jest.fn() } }));

const mockedAuthApi = jest.mocked(authApi);

function tokens(roles = ['admin']) {
  return {
    access_token: makeAccessToken({ roles }),
    refresh_token: 'refresh-2',
    token_type: 'bearer',
    expires_in: 900,
  };
}

beforeEach(() => {
  jest.resetAllMocks();
  jest.mocked(usersApi.list).mockResolvedValue(page([]));
  signOut();
});

describe('login', () => {
  it('inicia sesión con credenciales válidas y vuelve a la ruta pedida', async () => {
    mockedAuthApi.login.mockResolvedValue(tokens());
    const { router, user } = renderApp('/roles');

    expect(await screen.findByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('Email'), 'admin@example.com');
    await user.type(screen.getByLabelText('Contraseña'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/roles'));
    expect(mockedAuthApi.login).toHaveBeenCalledWith('admin@example.com', 'secret');
    expect(useAuthStore.getState().user?.roles).toEqual(['admin']);
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
  });

  it('muestra un error con credenciales inválidas', async () => {
    mockedAuthApi.login.mockRejectedValue(
      new ApiError(401, { code: 'invalid_credentials', message: 'invalid credentials' }),
    );
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'admin@example.com');
    await user.type(screen.getByLabelText('Contraseña'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email o contraseña incorrectos.');
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('informa del rate limit con el tiempo de espera', async () => {
    mockedAuthApi.login.mockRejectedValue(
      new ApiError(429, {
        code: 'rate_limited',
        message: 'too many',
        details: { retry_after_seconds: 42 },
      }),
    );
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'admin@example.com');
    await user.type(screen.getByLabelText('Contraseña'), 'x');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('42 s');
  });

  it('valida los campos antes de llamar al API', async () => {
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'no-es-email');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(screen.getByText('Introduce un email válido.')).toBeInTheDocument();
    expect(screen.getByText('Introduce tu contraseña.')).toBeInTheDocument();
    expect(mockedAuthApi.login).not.toHaveBeenCalled();
  });
});

describe('guards', () => {
  it('redirige a login si no hay sesión', async () => {
    const { router } = renderApp('/users');

    expect(await screen.findByRole('heading', { name: 'Iniciar sesión' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
  });

  it('deniega una ruta sin el rol requerido y oculta su enlace', async () => {
    signIn({ ...ADMIN, roles: ['user'], scopes: ['ai:use'] });
    renderApp('/roles');

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument();
  });
});

describe('sesión', () => {
  it('cierra sesión, revoca el refresh token y vuelve a login', async () => {
    mockedAuthApi.logout.mockResolvedValue(undefined);
    signIn();
    const { router, user } = renderApp('/users');

    await user.click(await screen.findByRole('button', { name: 'Cerrar sesión' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(mockedAuthApi.logout).toHaveBeenCalledWith('refresh-1');
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it('descarta la sesión local aunque el logout falle en el servidor', async () => {
    mockedAuthApi.logout.mockRejectedValue(
      new ApiError(0, { code: 'network_error', message: 'x' }),
    );
    signIn();

    await useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
  });

  it('refresca una sola vez aunque haya peticiones concurrentes', async () => {
    mockedAuthApi.refresh.mockResolvedValue(tokens(['auditor']));
    signIn();

    const results = await Promise.all([
      useAuthStore.getState().refresh(),
      useAuthStore.getState().refresh(),
    ]);

    expect(results).toEqual([true, true]);
    expect(mockedAuthApi.refresh).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().refreshToken).toBe('refresh-2');
    expect(useAuthStore.getState().user?.roles).toEqual(['auditor']);
  });

  it('muestra el aviso de sesión caducada al expirar', async () => {
    signIn();
    renderApp('/users');
    await screen.findByRole('heading', { name: 'Usuarios' });

    useAuthStore.getState().expire();

    expect(await screen.findByRole('status')).toHaveTextContent('Tu sesión ha caducado');
  });
});
