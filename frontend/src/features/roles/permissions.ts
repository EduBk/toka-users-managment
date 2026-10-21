import type { Role } from '@/types/domain';

/** Permissions seeded by role-service and checked by the services. */
export const KNOWN_PERMISSIONS = [
  'users:read',
  'users:write',
  'roles:read',
  'roles:write',
  'audit:read',
  'ai:use',
];

export function permissionCatalog(roles: Role[]): string[] {
  return [...new Set([...KNOWN_PERMISSIONS, ...roles.flatMap((role) => role.permissions)])].sort();
}
