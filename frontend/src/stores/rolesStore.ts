import { create } from 'zustand';

import { ApiError } from '@/services/apiClient';
import { authApi } from '@/services/authApi';
import { errorMessage } from '@/services/errorMessages';
import { rolesApi, type RoleInput } from '@/services/rolesApi';
import type { RequestStatus } from '@/types/api';
import type { Account, Role } from '@/types/domain';

export type AccountAccessStatus = RequestStatus | 'no-account';

interface RolesState {
  roles: Role[];
  status: RequestStatus;
  error: string | null;

  account: Account | null;
  accountRoles: Role[];
  accountPermissions: string[];
  accessStatus: AccountAccessStatus;
  accessError: string | null;

  mutationStatus: RequestStatus;
  mutationError: string | null;

  fetchRoles: () => Promise<void>;
  createRole: (input: RoleInput) => Promise<Role | null>;
  updatePermissions: (roleId: string, permissions: string[]) => Promise<Role | null>;
  loadAccountAccess: (email: string) => Promise<void>;
  assignRole: (roleId: string) => Promise<boolean>;
  revokeRole: (roleId: string) => Promise<boolean>;
}

export const useRolesStore = create<RolesState>()((set, get) => {
  async function mutate<T>(action: () => Promise<T>): Promise<T | null> {
    set({ mutationStatus: 'loading', mutationError: null });
    try {
      const result = await action();
      set({ mutationStatus: 'success' });
      return result;
    } catch (error) {
      set({ mutationStatus: 'error', mutationError: errorMessage(error) });
      return null;
    }
  }

  async function refreshAccess(accountId: string) {
    const [roles, permissions] = await Promise.all([
      rolesApi.userRoles(accountId),
      rolesApi.userPermissions(accountId),
    ]);
    set({ accountRoles: roles, accountPermissions: permissions.permissions });
  }

  function replaceRole(role: Role) {
    set({ roles: get().roles.map((item) => (item.id === role.id ? role : item)) });
  }

  return {
    roles: [],
    status: 'idle',
    error: null,
    account: null,
    accountRoles: [],
    accountPermissions: [],
    accessStatus: 'idle',
    accessError: null,
    mutationStatus: 'idle',
    mutationError: null,

    async fetchRoles() {
      set({ status: 'loading', error: null });
      try {
        set({ roles: await rolesApi.list(), status: 'success' });
      } catch (error) {
        set({ status: 'error', error: errorMessage(error) });
      }
    },

    createRole: (input) =>
      mutate(async () => {
        const role = await rolesApi.create(input);
        set({ roles: [...get().roles, role].sort((a, b) => a.name.localeCompare(b.name)) });
        return role;
      }),

    updatePermissions: (roleId, permissions) =>
      mutate(async () => {
        const role = await rolesApi.updatePermissions(roleId, permissions);
        replaceRole(role);
        return role;
      }),

    async loadAccountAccess(email) {
      set({
        account: null,
        accountRoles: [],
        accountPermissions: [],
        accessStatus: 'loading',
        accessError: null,
      });
      try {
        const account = await authApi.findAccount(email);
        set({ account });
        await refreshAccess(account.id);
        set({ accessStatus: 'success' });
      } catch (error) {
        if (error instanceof ApiError && error.code === 'account_not_found') {
          set({ accessStatus: 'no-account' });
          return;
        }
        set({ accessStatus: 'error', accessError: errorMessage(error) });
      }
    },

    async assignRole(roleId) {
      const account = get().account;
      if (!account) return false;
      const done = await mutate(async () => {
        await rolesApi.assign(account.id, roleId);
        await refreshAccess(account.id);
        return true;
      });
      return done === true;
    },

    async revokeRole(roleId) {
      const account = get().account;
      if (!account) return false;
      const done = await mutate(async () => {
        await rolesApi.revoke(account.id, roleId);
        await refreshAccess(account.id);
        return true;
      });
      return done === true;
    },
  };
});
