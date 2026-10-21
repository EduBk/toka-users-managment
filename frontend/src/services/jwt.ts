import type { SessionUser } from '@/types/domain';

interface AccessClaims {
  sub?: unknown;
  email?: unknown;
  roles?: unknown;
  scope?: unknown;
}

function decodeSegment(segment: string): unknown {
  const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
  const bytes = Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

/**
 * Reads the display claims of an access token. The signature is not verified
 * here: the backend validates every request, the UI only uses the claims to
 * decide what to show.
 */
export function readSessionUser(accessToken: string): SessionUser | null {
  const payload = accessToken.split('.')[1];
  if (!payload) return null;
  try {
    const claims = decodeSegment(payload) as AccessClaims;
    if (typeof claims.sub !== 'string' || typeof claims.email !== 'string') return null;
    return {
      id: claims.sub,
      email: claims.email,
      roles: Array.isArray(claims.roles)
        ? claims.roles.filter((role): role is string => typeof role === 'string')
        : [],
      scopes: typeof claims.scope === 'string' ? claims.scope.split(' ').filter(Boolean) : [],
    };
  } catch {
    return null;
  }
}
