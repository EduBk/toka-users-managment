import { screen } from '@testing-library/react';

import { usersApi } from '@/services/usersApi';
import { page } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { signIn } from '@/test/session';

jest.mock('@/services/usersApi', () => ({ usersApi: { list: jest.fn() } }));

describe('routes', () => {
  beforeEach(() => {
    jest.mocked(usersApi.list).mockResolvedValue(page([]));
    signIn();
  });

  it('redirige la raíz a usuarios dentro del layout', async () => {
    const { router } = renderApp('/');

    expect(await screen.findByRole('heading', { name: 'Usuarios' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/users');
    expect(screen.getByRole('navigation', { name: 'Principal' })).toBeInTheDocument();
  });

  it('muestra la página 404 en rutas desconocidas', async () => {
    renderApp('/no-existe');

    expect(
      await screen.findByRole('heading', { name: 'Página no encontrada' }),
    ).toBeInTheDocument();
  });
});
