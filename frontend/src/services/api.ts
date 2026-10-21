import { API_BASE_URL } from '@/app/config';
import { createApiClient } from '@/services/apiClient';

export const api = createApiClient(API_BASE_URL);
