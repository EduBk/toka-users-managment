import { create } from 'zustand';

import { auditApi, type AuditFilters } from '@/services/auditApi';
import { errorMessage } from '@/services/errorMessages';
import type { RequestStatus } from '@/types/api';
import type { AuditEntry } from '@/types/domain';

interface AuditState {
  items: AuditEntry[];
  total: number;
  page: number;
  pageSize: number;
  filters: AuditFilters;
  status: RequestStatus;
  error: string | null;

  fetchPage: (page?: number) => Promise<void>;
  applyFilters: (filters: AuditFilters) => Promise<void>;
}

export const useAuditStore = create<AuditState>()((set, get) => ({
  items: [],
  total: 0,
  page: 1,
  pageSize: 20,
  filters: {},
  status: 'idle',
  error: null,

  async fetchPage(page = get().page) {
    set({ status: 'loading', error: null, page });
    try {
      const result = await auditApi.search(get().filters, page, get().pageSize);
      set({ items: result.items, total: result.total, page: result.page, status: 'success' });
    } catch (error) {
      set({ status: 'error', error: errorMessage(error) });
    }
  },

  applyFilters(filters) {
    set({ filters });
    return get().fetchPage(1);
  },
}));
