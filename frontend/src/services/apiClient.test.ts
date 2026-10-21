import { ApiError, createApiClient, type SessionHandlers } from '@/services/apiClient';
import { fakeResponse as jsonResponse } from '@/test/http';

function sessionWith(overrides: Partial<SessionHandlers> = {}): SessionHandlers {
  return {
    getAccessToken: () => 'token-1',
    refreshSession: jest.fn().mockResolvedValue(false),
    onSessionExpired: jest.fn(),
    ...overrides,
  };
}

describe('createApiClient', () => {
  it('envía el JWT, serializa el body y omite parámetros vacíos', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(200, { ok: true }));
    const client = createApiClient('/api', fetchFn);
    client.setSessionHandlers(sessionWith());

    const result = await client.request('/users', {
      method: 'POST',
      body: { name: 'Ana' },
      query: { page: 2, email: '', type: undefined },
    });

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe('/api/users?page=2');
    expect(init.headers.Authorization).toBe('Bearer token-1');
    expect(init.body).toBe(JSON.stringify({ name: 'Ana' }));
  });

  it('no envía el JWT cuando auth es false', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(200, {}));
    const client = createApiClient('/api', fetchFn);
    client.setSessionHandlers(sessionWith());

    await client.request('/auth/login', { method: 'POST', body: {}, auth: false });

    expect(fetchFn.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it('convierte el esquema de error del backend en ApiError', async () => {
    const fetchFn = jest
      .fn()
      .mockResolvedValue(jsonResponse(409, { code: 'email_already_exists', message: 'Duplicado' }));
    const client = createApiClient('/api', fetchFn);

    await expect(client.request('/users')).rejects.toMatchObject({
      status: 409,
      code: 'email_already_exists',
      message: 'Duplicado',
    });
  });

  it('usa un error genérico si la respuesta no tiene el esquema esperado', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(502, '<html>'));
    const client = createApiClient('/api', fetchFn);

    await expect(client.request('/users')).rejects.toMatchObject({
      status: 502,
      code: 'unexpected_response',
    });
  });

  it('devuelve network_error si fetch falla', async () => {
    const fetchFn = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    const client = createApiClient('/api', fetchFn);

    const error = await client.request('/users').catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe('network_error');
  });

  it('devuelve undefined en respuestas 204', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(204));
    const client = createApiClient('/api', fetchFn);

    await expect(client.request('/users/1', { method: 'DELETE' })).resolves.toBeUndefined();
  });

  it('refresca la sesión ante un 401 y reintenta una vez', async () => {
    let token = 'expired';
    const fetchFn = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { code: 'invalid_token', message: 'x' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: '1' }));
    const session = sessionWith({
      getAccessToken: () => token,
      refreshSession: jest.fn().mockImplementation(async () => {
        token = 'fresh';
        return true;
      }),
    });
    const client = createApiClient('/api', fetchFn);
    client.setSessionHandlers(session);

    await expect(client.request('/users/1')).resolves.toEqual({ id: '1' });
    expect(fetchFn.mock.calls[1][1].headers.Authorization).toBe('Bearer fresh');
    expect(session.onSessionExpired).not.toHaveBeenCalled();
  });

  it('expira la sesión si el refresh falla', async () => {
    const fetchFn = jest
      .fn()
      .mockResolvedValue(jsonResponse(401, { code: 'invalid_token', message: 'x' }));
    const session = sessionWith();
    const client = createApiClient('/api', fetchFn);
    client.setSessionHandlers(session);

    await expect(client.request('/users')).rejects.toMatchObject({ status: 401 });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(session.onSessionExpired).toHaveBeenCalledTimes(1);
  });
});
