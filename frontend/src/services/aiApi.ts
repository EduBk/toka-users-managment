import { api } from '@/services/api';
import type { AssistantAnswer } from '@/types/domain';

export interface AssistantHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AskInput {
  question: string;
  history?: AssistantHistoryMessage[];
  includeSystemData?: boolean;
}

export interface ReindexReport {
  documents_seen: number;
  documents_indexed: number;
  documents_skipped: number;
  documents_deleted: number;
  chunks_indexed: number;
  embedding_tokens: number;
}

export const aiApi = {
  ask: (input: AskInput) =>
    api.request<AssistantAnswer>('/ai/ask', {
      method: 'POST',
      body: {
        question: input.question,
        history: input.history ?? [],
        include_system_data: input.includeSystemData ?? false,
      },
    }),

  reindex: () => api.request<ReindexReport>('/ai/reindex', { method: 'POST' }),
};
