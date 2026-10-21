import { create } from 'zustand';

import { api } from '@/services/api';
import { ApiError } from '@/services/apiClient';
import { authApi, type TokenPair } from '@/services/authApi';
import { readSessionUser } from '@/services/jwt';
import type { RequestStatus } from '@/types/api';
import type { SessionUser } from '@/types/domain';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: SessionUser | null;
  status: RequestStatus;
  error: string | null;
  sessionExpired: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  refresh: () => Promise<boolean>;
  logout: () => Promise<void>;
  expire: () => void;
}

const SIGNED_OUT = {
  accessToken: null,
  refreshToken: null,
  user: null,
} as const;

export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Email o contraseña incorrectos.';
    if (error.status === 429) {
      const retryAfter = (error.details as { retry_after_seconds?: number } | null)
        ?.retry_after_seconds;
      return retryAfter
        ? `Demasiados intentos. Vuelve a intentarlo en ${retryAfter} s.`
        : 'Demasiados intentos. Vuelve a intentarlo en unos segundos.';
    }
    return error.message;
  }
  return 'No se pudo iniciar sesión.';
}

let pendingRefresh: Promise<boolean> | null = null;

export const useAuthStore = create<AuthState>()((set, get) => {
  function startSession(tokens: TokenPair): boolean {
    const user = readSessionUser(tokens.access_token);
    if (!user) return false;
    set({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      user,
      status: 'success',
      error: null,
      sessionExpired: false,
    });
    return true;
  }

  return {
    ...SIGNED_OUT,
    status: 'idle',
    error: null,
    sessionExpired: false,

    async login(email, password) {
      set({ status: 'loading', error: null });
      try {
        if (startSession(await authApi.login(email, password))) return true;
        set({ status: 'error', error: 'El servidor devolvió un token no válido.' });
      } catch (error) {
        set({ status: 'error', error: loginErrorMessage(error) });
      }
      return false;
    },

    refresh() {
      const refreshToken = get().refreshToken;
      if (!refreshToken) return Promise.resolve(false);
      pendingRefresh ??= authApi
        .refresh(refreshToken)
        .then(startSession)
        .catch(() => false)
        .finally(() => {
          pendingRefresh = null;
        });
      return pendingRefresh;
    },

    async logout() {
      const refreshToken = get().refreshToken;
      try {
        if (refreshToken) await authApi.logout(refreshToken);
      } catch {
        // The local session is discarded even if the server could not revoke it.
      }
      set({ ...SIGNED_OUT, status: 'idle', error: null, sessionExpired: false });
    },

    expire() {
      if (!get().user) return;
      set({ ...SIGNED_OUT, status: 'idle', error: null, sessionExpired: true });
    },
  };
});

api.setSessionHandlers({
  getAccessToken: () => useAuthStore.getState().accessToken,
  refreshSession: () => useAuthStore.getState().refresh(),
  onSessionExpired: () => useAuthStore.getState().expire(),
});
