import { useAuthStore } from '@/stores/authStore';
import type { SessionUser } from '@/types/domain';

function base64Url(value: object): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

export function makeAccessToken(user: Partial<SessionUser> = {}): string {
  const claims = {
    sub: user.id ?? '11111111-1111-4111-8111-111111111111',
    email: user.email ?? 'admin@example.com',
    roles: user.roles ?? ['admin'],
    scope: (user.scopes ?? ['users:read', 'users:write', 'roles:read', 'roles:write']).join(' '),
  };
  return `${base64Url({ alg: 'RS256' })}.${base64Url(claims)}.signature`;
}

export const ADMIN: SessionUser = {
  id: '11111111-1111-4111-8111-111111111111',
  email: 'admin@example.com',
  roles: ['admin'],
  scopes: ['users:read', 'users:write', 'roles:read', 'roles:write', 'audit:read'],
};

export function signIn(user: SessionUser = ADMIN) {
  useAuthStore.setState({
    accessToken: makeAccessToken(user),
    refreshToken: 'refresh-1',
    user,
    status: 'success',
    error: null,
    sessionExpired: false,
  });
}

export function signOut() {
  useAuthStore.setState({
    accessToken: null,
    refreshToken: null,
    user: null,
    status: 'idle',
    error: null,
    sessionExpired: false,
  });
}
