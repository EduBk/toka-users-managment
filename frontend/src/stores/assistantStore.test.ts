import { aiApi } from '@/services/aiApi';
import { ApiError } from '@/services/apiClient';
import { MAX_HISTORY_MESSAGES, useAssistantStore } from '@/stores/assistantStore';
import { makeAssistantAnswer } from '@/test/fixtures';
import type { AssistantAnswer } from '@/types/domain';

jest.mock('@/services/aiApi', () => ({ aiApi: { ask: jest.fn(), reindex: jest.fn() } }));

const mockedAsk = jest.mocked(aiApi.ask);
const mockedReindex = jest.mocked(aiApi.reindex);

const REPORT = {
  documents_seen: 13,
  documents_indexed: 13,
  documents_skipped: 0,
  documents_deleted: 0,
  chunks_indexed: 208,
  embedding_tokens: 0,
};

function resetStore() {
  useAssistantStore.setState({
    messages: [],
    status: 'idle',
    error: null,
    includeSystemData: false,
    lastQuestion: null,
    reindexStatus: 'idle',
    reindexResult: null,
    reindexError: null,
  });
}

beforeEach(() => {
  jest.resetAllMocks();
  resetStore();
});

describe('assistantStore', () => {
  it('pasa por loading y añade la pregunta y la respuesta', async () => {
    let resolve: (value: AssistantAnswer) => void = () => {};
    mockedAsk.mockReturnValue(new Promise((done) => (resolve = done)));

    const pending = useAssistantStore.getState().ask('  ¿Roles?  ');
    expect(useAssistantStore.getState()).toMatchObject({
      status: 'loading',
      lastQuestion: '¿Roles?',
      error: null,
    });
    expect(useAssistantStore.getState().messages).toEqual([
      { id: expect.any(String), role: 'user', content: '¿Roles?' },
    ]);

    resolve(makeAssistantAnswer());
    await expect(pending).resolves.toBe(true);
    expect(useAssistantStore.getState()).toMatchObject({ status: 'success', error: null });
    expect(useAssistantStore.getState().messages[1]).toMatchObject({
      role: 'assistant',
      content: 'Cada servicio valida el JWT localmente con el JWKS de auth-service [1].',
    });
  });

  it('no llama al API con una pregunta vacía', async () => {
    await expect(useAssistantStore.getState().ask('   ')).resolves.toBe(false);

    expect(mockedAsk).not.toHaveBeenCalled();
    expect(useAssistantStore.getState().messages).toEqual([]);
  });

  it('guarda el error y conserva la pregunta para reintentar', async () => {
    mockedAsk.mockRejectedValueOnce(new ApiError(429, { code: 'ai_rate_limited', message: 'x' }));

    await expect(useAssistantStore.getState().ask('¿Roles?')).resolves.toBe(false);

    expect(useAssistantStore.getState()).toMatchObject({
      status: 'error',
      error: 'Has hecho demasiadas consultas seguidas. Espera un momento y vuelve a intentarlo.',
      lastQuestion: '¿Roles?',
    });
    expect(useAssistantStore.getState().messages).toHaveLength(1);
  });

  it('reintenta sin duplicar la pregunta ni reenviarla en el historial', async () => {
    mockedAsk.mockResolvedValueOnce(makeAssistantAnswer());
    useAssistantStore.setState({
      messages: [{ id: 'm1', role: 'user', content: '¿Roles?' }],
      lastQuestion: '¿Roles?',
      status: 'error',
      error: 'x',
    });

    await expect(useAssistantStore.getState().retry()).resolves.toBe(true);

    expect(mockedAsk).toHaveBeenCalledWith({
      question: '¿Roles?',
      history: [],
      includeSystemData: false,
    });
    expect(useAssistantStore.getState().messages).toHaveLength(2);
  });

  it('no reintenta sin una pregunta previa', async () => {
    await expect(useAssistantStore.getState().retry()).resolves.toBe(false);

    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it('limita el historial a los últimos mensajes', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const messages = Array.from({ length: MAX_HISTORY_MESSAGES + 2 }, (_, index) => ({
      id: `m${index}`,
      role: (index % 2 === 0 ? 'user' : 'assistant') as 'user' | 'assistant',
      content: `mensaje ${index}`,
    }));
    useAssistantStore.setState({ messages });

    await useAssistantStore.getState().ask('nueva');

    const history = mockedAsk.mock.calls[0]?.[0]?.history ?? [];
    expect(history).toHaveLength(MAX_HISTORY_MESSAGES);
    expect(history[0]).toEqual({
      role: 'user',
      content: `mensaje ${messages.length - MAX_HISTORY_MESSAGES}`,
    });
  });

  it('envía la opción de datos del sistema', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    useAssistantStore.getState().setIncludeSystemData(true);

    await useAssistantStore.getState().ask('¿Usuarios?');

    expect(mockedAsk).toHaveBeenCalledWith(expect.objectContaining({ includeSystemData: true }));
  });

  it('reinicia la conversación', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    await useAssistantStore.getState().ask('¿Roles?');

    useAssistantStore.getState().reset();

    expect(useAssistantStore.getState()).toMatchObject({
      messages: [],
      status: 'idle',
      error: null,
      lastQuestion: null,
    });
  });

  it('reindexa la documentación y guarda el reporte', async () => {
    mockedReindex.mockResolvedValue(REPORT);

    const result = await useAssistantStore.getState().reindex();

    expect(result).toEqual(REPORT);
    expect(useAssistantStore.getState()).toMatchObject({
      reindexStatus: 'success',
      reindexResult: REPORT,
      reindexError: null,
    });
  });

  it('guarda el error de reindexación', async () => {
    mockedReindex.mockRejectedValue(new ApiError(500, { code: 'reindex_failed', message: 'x' }));

    const result = await useAssistantStore.getState().reindex();

    expect(result).toBeNull();
    expect(useAssistantStore.getState()).toMatchObject({
      reindexStatus: 'error',
      reindexResult: null,
      reindexError: 'No se pudo reindexar la documentación. Inténtalo de nuevo.',
    });
  });
});
