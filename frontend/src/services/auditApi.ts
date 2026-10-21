import { api } from '@/services/api';
import type { Page } from '@/types/api';
import type { AuditEntry } from '@/types/domain';

export interface AuditFilters {
  user?: string;
  type?: string;
  from?: string;
  to?: string;
}

export const auditApi = {
  search: (filters: AuditFilters, page: number, pageSize: number) =>
    api.request<Page<AuditEntry>>('/audit', {
      query: { ...filters, page, page_size: pageSize },
    }),
};
