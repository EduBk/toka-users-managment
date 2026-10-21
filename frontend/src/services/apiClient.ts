import type { ApiErrorBody } from '@/types/api';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

export interface SessionHandlers {
  getAccessToken: () => string | null;
  refreshSession: () => Promise<boolean>;
  onSessionExpired: () => void;
}

export type QueryValue = string | number | undefined | null;

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, QueryValue>;
  auth?: boolean;
}

export interface ApiClient {
  request<T>(path: string, options?: RequestOptions): Promise<T>;
  setSessionHandlers(handlers: SessionHandlers): void;
}

const NETWORK_ERROR: ApiErrorBody = {
  code: 'network_error',
  message: 'No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.',
};

const UNEXPECTED_RESPONSE: ApiErrorBody = {
  code: 'unexpected_response',
  message: 'El servidor devolvió una respuesta inesperada.',
};

function buildUrl(baseUrl: string, path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  }
  const search = params.toString();
  return `${baseUrl}${path}${search ? `?${search}` : ''}`;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ApiErrorBody).code === 'string' &&
    typeof (value as ApiErrorBody).message === 'string'
  );
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export function createApiClient(
  baseUrl: string,
  fetchFn: typeof fetch = (input, init) => fetch(input, init),
): ApiClient {
  let session: SessionHandlers | null = null;

  async function send(path: string, options: RequestOptions): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    const token = options.auth === false ? null : session?.getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
      return await fetchFn(buildUrl(baseUrl, path, options.query), {
        method: options.method ?? 'GET',
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch {
      throw new ApiError(0, NETWORK_ERROR);
    }
  }

  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    let response = await send(path, options);
    if (response.status === 401 && options.auth !== false && session) {
      if (await session.refreshSession()) {
        response = await send(path, options);
      }
      if (response.status === 401) session.onSessionExpired();
    }
    const payload = await readJson(response);
    if (!response.ok) {
      throw new ApiError(response.status, isApiErrorBody(payload) ? payload : UNEXPECTED_RESPONSE);
    }
    return payload as T;
  }

  return {
    request,
    setSessionHandlers(handlers) {
      session = handlers;
    },
  };
}
