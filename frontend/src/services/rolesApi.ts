import { api } from '@/services/api';
import type { Role } from '@/types/domain';

export interface RoleInput {
  name: string;
  description: string;
  permissions: string[];
}

const userPath = (accountId: string) => `/users/${encodeURIComponent(accountId)}`;

export const rolesApi = {
  list: () => api.request<Role[]>('/roles'),
  create: (input: RoleInput) => api.request<Role>('/roles', { method: 'POST', body: input }),
  updatePermissions: (roleId: string, permissions: string[]) =>
    api.request<Role>(`/roles/${encodeURIComponent(roleId)}/permissions`, {
      method: 'PUT',
      body: { permissions },
    }),
  userRoles: (accountId: string) => api.request<Role[]>(`${userPath(accountId)}/roles`),
  userPermissions: (accountId: string) =>
    api.request<{ user_id: string; permissions: string[] }>(`${userPath(accountId)}/permissions`),
  assign: (accountId: string, roleId: string) =>
    api.request<void>(`${userPath(accountId)}/roles`, {
      method: 'POST',
      body: { role_id: roleId },
    }),
  revoke: (accountId: string, roleId: string) =>
    api.request<void>(`${userPath(accountId)}/roles/${encodeURIComponent(roleId)}`, {
      method: 'DELETE',
    }),
};
