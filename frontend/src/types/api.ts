export type RequestStatus = 'idle' | 'loading' | 'success' | 'error';

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
