import { create } from 'zustand';

import { errorMessage } from '@/services/errorMessages';
import { usersApi, type UserInput } from '@/services/usersApi';
import type { RequestStatus } from '@/types/api';
import type { User } from '@/types/domain';

interface UsersState {
  items: User[];
  total: number;
  page: number;
  pageSize: number;
  status: RequestStatus;
  error: string | null;

  selected: User | null;
  selectedStatus: RequestStatus;
  selectedError: string | null;

  mutationStatus: RequestStatus;
  mutationError: string | null;

  fetchPage: (page?: number) => Promise<void>;
  fetchUser: (id: string) => Promise<void>;
  createUser: (input: UserInput) => Promise<User | null>;
  updateUser: (id: string, input: Partial<UserInput>) => Promise<User | null>;
  deactivateUser: (id: string) => Promise<boolean>;
}

export const useUsersStore = create<UsersState>()((set, get) => {
  async function mutate<T>(action: () => Promise<T>): Promise<T | null> {
    set({ mutationStatus: 'loading', mutationError: null });
    try {
      const result = await action();
      set({ mutationStatus: 'success' });
      void get().fetchPage();
      return result;
    } catch (error) {
      set({ mutationStatus: 'error', mutationError: errorMessage(error) });
      return null;
    }
  }

  return {
    items: [],
    total: 0,
    page: 1,
    pageSize: 20,
    status: 'idle',
    error: null,
    selected: null,
    selectedStatus: 'idle',
    selectedError: null,
    mutationStatus: 'idle',
    mutationError: null,

    async fetchPage(page = get().page) {
      set({ status: 'loading', error: null, page });
      try {
        const result = await usersApi.list(page, get().pageSize);
        set({ items: result.items, total: result.total, page: result.page, status: 'success' });
      } catch (error) {
        set({ status: 'error', error: errorMessage(error) });
      }
    },

    async fetchUser(id) {
      set({ selectedStatus: 'loading', selectedError: null });
      try {
        set({ selected: await usersApi.get(id), selectedStatus: 'success' });
      } catch (error) {
        set({ selected: null, selectedStatus: 'error', selectedError: errorMessage(error) });
      }
    },

    createUser: (input) => mutate(() => usersApi.create(input)),

    updateUser: (id, input) =>
      mutate(async () => {
        const user = await usersApi.update(id, input);
        set({ selected: user });
        return user;
      }),

    async deactivateUser(id) {
      const done = await mutate(async () => {
        await usersApi.deactivate(id);
        const selected = get().selected;
        if (selected?.id === id) set({ selected: { ...selected, status: 'inactive' } });
        return true;
      });
      return done === true;
    },
  };
});
