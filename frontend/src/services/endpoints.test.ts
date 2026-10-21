import { api } from '@/services/api';
import { aiApi } from '@/services/aiApi';
import { auditApi } from '@/services/auditApi';
import { authApi } from '@/services/authApi';
import { rolesApi } from '@/services/rolesApi';
import { usersApi } from '@/services/usersApi';

jest.mock('@/services/api', () => ({ api: { request: jest.fn() } }));

const request = jest.mocked(api.request);

beforeEach(() => request.mockReset().mockResolvedValue(undefined));

describe('endpoints del API', () => {
  it('auth-service', async () => {
    await authApi.login('a@b.co', 'secret');
    await authApi.refresh('rt');
    await authApi.logout('rt');
    await authApi.findAccount('a@b.co');

    expect(request.mock.calls).toEqual([
      [
        '/auth/login',
        { method: 'POST', body: { email: 'a@b.co', password: 'secret' }, auth: false },
      ],
      ['/auth/refresh', { method: 'POST', body: { refresh_token: 'rt' }, auth: false }],
      ['/auth/logout', { method: 'POST', body: { refresh_token: 'rt' } }],
      ['/auth/accounts', { query: { email: 'a@b.co' } }],
    ]);
  });

  it('user-service', async () => {
    await usersApi.list(2, 20);
    await usersApi.get('u 1');
    await usersApi.create({ email: 'a@b.co', name: 'A' });
    await usersApi.update('u1', { name: 'B' });
    await usersApi.deactivate('u1');

    expect(request.mock.calls).toEqual([
      ['/users', { query: { page: 2, page_size: 20 } }],
      ['/users/u%201'],
      ['/users', { method: 'POST', body: { email: 'a@b.co', name: 'A' } }],
      ['/users/u1', { method: 'PATCH', body: { name: 'B' } }],
      ['/users/u1', { method: 'DELETE' }],
    ]);
  });

  it('role-service', async () => {
    await rolesApi.list();
    await rolesApi.create({ name: 'editor', description: '', permissions: [] });
    await rolesApi.updatePermissions('r1', ['users:read']);
    await rolesApi.userRoles('acc1');
    await rolesApi.userPermissions('acc1');
    await rolesApi.assign('acc1', 'r1');
    await rolesApi.revoke('acc1', 'r1');

    expect(request.mock.calls).toEqual([
      ['/roles'],
      ['/roles', { method: 'POST', body: { name: 'editor', description: '', permissions: [] } }],
      ['/roles/r1/permissions', { method: 'PUT', body: { permissions: ['users:read'] } }],
      ['/users/acc1/roles'],
      ['/users/acc1/permissions'],
      ['/users/acc1/roles', { method: 'POST', body: { role_id: 'r1' } }],
      ['/users/acc1/roles/r1', { method: 'DELETE' }],
    ]);
  });

  it('audit-service', async () => {
    await auditApi.search({ type: 'user.created' }, 1, 20);

    expect(request).toHaveBeenCalledWith('/audit', {
      query: { type: 'user.created', page: 1, page_size: 20 },
    });
  });

  it('ai-service', async () => {
    await aiApi.ask({
      question: '¿Qué roles existen?',
      history: [{ role: 'user', content: 'hola' }],
      includeSystemData: true,
    });
    await aiApi.reindex();

    expect(request.mock.calls).toEqual([
      [
        '/ai/ask',
        {
          method: 'POST',
          body: {
            question: '¿Qué roles existen?',
            history: [{ role: 'user', content: 'hola' }],
            include_system_data: true,
          },
        },
      ],
      ['/ai/reindex', { method: 'POST' }],
    ]);
  });
});
