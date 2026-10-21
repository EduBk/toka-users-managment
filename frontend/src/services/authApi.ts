import { api } from '@/services/api';
import type { Account } from '@/types/domain';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.request<TokenPair>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    }),
  refresh: (refreshToken: string) =>
    api.request<TokenPair>('/auth/refresh', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      auth: false,
    }),
  logout: (refreshToken: string) =>
    api.request<void>('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } }),
  findAccount: (email: string) => api.request<Account>('/auth/accounts', { query: { email } }),
};
