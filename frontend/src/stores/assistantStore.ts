import { create } from 'zustand';

import { aiApi, type AssistantHistoryMessage, type ReindexReport } from '@/services/aiApi';
import { errorMessage } from '@/services/errorMessages';
import type { RequestStatus } from '@/types/api';
import type { AssistantAnswer } from '@/types/domain';

export type AssistantStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  answer?: AssistantAnswer;
}

interface AssistantState {
  messages: AssistantMessage[];
  status: AssistantStatus;
  error: string | null;
  includeSystemData: boolean;
  lastQuestion: string | null;
  reindexStatus: RequestStatus;
  reindexResult: ReindexReport | null;
  reindexError: string | null;

  ask: (question: string) => Promise<boolean>;
  retry: () => Promise<boolean>;
  reset: () => void;
  setIncludeSystemData: (value: boolean) => void;
  reindex: () => Promise<ReindexReport | null>;
}

export const MAX_HISTORY_MESSAGES = 6;

let nextMessageId = 1;

function messageId(): string {
  return `m${nextMessageId++}`;
}

function historyOf(
  messages: AssistantMessage[],
  dropTrailingUser: boolean,
): AssistantHistoryMessage[] {
  const usable =
    dropTrailingUser && messages.at(-1)?.role === 'user' ? messages.slice(0, -1) : messages;
  return usable.slice(-MAX_HISTORY_MESSAGES).map(({ role, content }) => ({ role, content }));
}

export const useAssistantStore = create<AssistantState>()((set, get) => {
  async function request(question: string, history: AssistantHistoryMessage[]): Promise<boolean> {
    set({ status: 'loading', error: null });
    try {
      const answer = await aiApi.ask({
        question,
        history,
        includeSystemData: get().includeSystemData,
      });
      set((state) => ({
        status: 'success',
        messages: [
          ...state.messages,
          { id: messageId(), role: 'assistant', content: answer.answer, answer },
        ],
      }));
      return true;
    } catch (error) {
      set({ status: 'error', error: errorMessage(error) });
      return false;
    }
  }

  return {
    messages: [],
    status: 'idle',
    error: null,
    includeSystemData: false,
    lastQuestion: null,
    reindexStatus: 'idle',
    reindexResult: null,
    reindexError: null,

    async ask(question) {
      const text = question.trim();
      if (!text) return false;
      const history = historyOf(get().messages, false);
      set((state) => ({
        messages: [...state.messages, { id: messageId(), role: 'user', content: text }],
        lastQuestion: text,
        status: 'loading',
        error: null,
      }));
      return request(text, history);
    },

    async retry() {
      const question = get().lastQuestion;
      if (!question) return false;
      return request(question, historyOf(get().messages, true));
    },

    reset() {
      set({ messages: [], status: 'idle', error: null, lastQuestion: null });
    },

    setIncludeSystemData(value) {
      set({ includeSystemData: value });
    },

    async reindex() {
      set({ reindexStatus: 'loading', reindexError: null });
      try {
        const result = await aiApi.reindex();
        set({ reindexStatus: 'success', reindexResult: result });
        return result;
      } catch (error) {
        set({
          reindexStatus: 'error',
          reindexError: errorMessage(error, 'No se pudo reindexar la documentación.'),
        });
        return null;
      }
    },
  };
});
