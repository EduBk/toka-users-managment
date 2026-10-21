import { readSessionUser } from '@/services/jwt';
import { makeAccessToken } from '@/test/session';

describe('readSessionUser', () => {
  it('lee sub, email, roles y scopes del access token', () => {
    const token = makeAccessToken({
      email: 'ana@example.com',
      roles: ['auditor'],
      scopes: ['audit:read'],
    });

    expect(readSessionUser(token)).toMatchObject({
      email: 'ana@example.com',
      roles: ['auditor'],
      scopes: ['audit:read'],
    });
  });

  it('devuelve null si el token no es un JWT legible', () => {
    expect(readSessionUser('basura')).toBeNull();
    expect(readSessionUser('a.b.c')).toBeNull();
  });
});
