import { api } from '@/services/api';
import type { Page } from '@/types/api';
import type { User } from '@/types/domain';

export interface UserInput {
  email: string;
  name: string;
}

export const usersApi = {
  list: (page: number, pageSize: number) =>
    api.request<Page<User>>('/users', { query: { page, page_size: pageSize } }),
  get: (id: string) => api.request<User>(`/users/${encodeURIComponent(id)}`),
  create: (input: UserInput) => api.request<User>('/users', { method: 'POST', body: input }),
  update: (id: string, input: Partial<UserInput>) =>
    api.request<User>(`/users/${encodeURIComponent(id)}`, { method: 'PATCH', body: input }),
  deactivate: (id: string) =>
    api.request<void>(`/users/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};
