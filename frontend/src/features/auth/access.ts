import type { SessionUser } from '@/types/domain';

export interface AccessRule {
  /** Any of these roles grants access. */
  roles?: string[];
  /** All of these scopes are required. */
  scopes?: string[];
}

export function hasAccess(user: SessionUser | null, rule: AccessRule = {}): boolean {
  if (!user) return false;
  const rolesOk = !rule.roles?.length || rule.roles.some((role) => user.roles.includes(role));
  const scopesOk = (rule.scopes ?? []).every((scope) => user.scopes.includes(scope));
  return rolesOk && scopesOk;
}

export const ACCESS = {
  usersRead: { scopes: ['users:read'] },
  usersWrite: { scopes: ['users:write'] },
  rolesAdmin: { roles: ['admin'] },
  audit: { roles: ['auditor', 'admin'] },
  aiUse: { scopes: ['ai:use'] },
} satisfies Record<string, AccessRule>;
