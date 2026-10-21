import { screen, within } from '@testing-library/react';

import { aiApi } from '@/services/aiApi';
import { ApiError } from '@/services/apiClient';
import { useAssistantStore } from '@/stores/assistantStore';
import { makeAssistantAnswer } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { ADMIN, signIn } from '@/test/session';
import type { SessionUser } from '@/types/domain';

jest.mock('@/services/aiApi', () => ({ aiApi: { ask: jest.fn(), reindex: jest.fn() } }));

const mockedAsk = jest.mocked(aiApi.ask);
const mockedReindex = jest.mocked(aiApi.reindex);
const AI_USER: SessionUser = { ...ADMIN, scopes: [...ADMIN.scopes, 'ai:use'] };
const AI_ONLY: SessionUser = { ...ADMIN, scopes: ['ai:use'] };
const AI_READER: SessionUser = {
  ...ADMIN,
  roles: ['user'],
  scopes: ['ai:use', 'users:read'],
};

const REPORT = {
  documents_seen: 13,
  documents_indexed: 2,
  documents_skipped: 11,
  documents_deleted: 0,
  chunks_indexed: 20,
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
  signIn(AI_USER);
});

describe('vista del asistente', () => {
  it('envía la pregunta y muestra respuesta, fuentes y métricas', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    expect(screen.getByRole('heading', { name: 'Asistente' })).toBeInTheDocument();
    expect(screen.getByText('¿Qué quieres saber?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preguntar' })).toBeDisabled();

    await user.type(screen.getByLabelText('Tu pregunta'), '¿Cómo se validan los tokens?');
    await user.click(screen.getByRole('button', { name: 'Preguntar' }));

    expect(await screen.findByText(/Cada servicio valida el JWT/)).toBeInTheDocument();
    const question = screen.getByRole('article', { name: 'Pregunta enviada' });
    const answer = screen.getByRole('article', { name: 'Respuesta del asistente' });
    expect(within(question).getByText('Tú')).toBeInTheDocument();
    expect(within(answer).getByText('Asistente')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Fuentes' })).toBeInTheDocument();
    expect(screen.getByText('arquitectura/flujos-de-datos.md')).toBeInTheDocument();
    expect(screen.getByText('35 tokens')).toBeInTheDocument();
    expect(mockedAsk).toHaveBeenCalledWith({
      question: '¿Cómo se validan los tokens?',
      history: [],
      includeSystemData: false,
    });
  });

  it('envía con Intro y respeta Mayús+Intro para el salto de línea', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');
    const textarea = screen.getByLabelText('Tu pregunta');

    await user.type(textarea, '¿Roles?{Enter}');
    await screen.findByText(/Cada servicio valida el JWT/);
    expect(mockedAsk).toHaveBeenCalledTimes(1);

    await user.type(textarea, 'linea1{Shift>}{Enter}{/Shift}linea2');
    expect(textarea).toHaveValue('linea1\nlinea2');
    expect(mockedAsk).toHaveBeenCalledTimes(1);
  });

  it('mantiene el historial corto entre preguntas', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    await user.type(screen.getByLabelText('Tu pregunta'), 'primera{Enter}');
    await screen.findByText(/Cada servicio valida el JWT/);
    await user.type(screen.getByLabelText('Tu pregunta'), 'segunda{Enter}');
    await screen.findAllByText(/Cada servicio valida el JWT/);

    expect(mockedAsk).toHaveBeenLastCalledWith({
      question: 'segunda',
      history: [
        { role: 'user', content: 'primera' },
        {
          role: 'assistant',
          content: 'Cada servicio valida el JWT localmente con el JWKS de auth-service [1].',
        },
      ],
      includeSystemData: false,
    });
  });

  it('incluye los datos del sistema cuando el usuario lo pide', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    await user.click(screen.getByLabelText('Incluir datos del sistema (usuarios y roles)'));
    await user.type(screen.getByLabelText('Tu pregunta'), '¿Cuántos usuarios hay?{Enter}');

    await screen.findByText(/Cada servicio valida el JWT/);
    expect(mockedAsk).toHaveBeenCalledWith(expect.objectContaining({ includeSystemData: true }));
  });

  it('oculta los datos del sistema sin permiso de lectura de usuarios', async () => {
    signIn(AI_ONLY);
    renderApp('/assistant');

    expect(
      screen.queryByLabelText('Incluir datos del sistema (usuarios y roles)'),
    ).not.toBeInTheDocument();
  });

  it('sugiere preguntas de ejemplo y las envía al pulsarlas', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    await user.click(
      screen.getByRole('button', { name: '¿Qué microservicios forman el sistema?' }),
    );

    await screen.findByText(/Cada servicio valida el JWT/);
    expect(mockedAsk).toHaveBeenCalledWith(
      expect.objectContaining({ question: '¿Qué microservicios forman el sistema?' }),
    );
  });

  it('muestra el error traducido y permite reintentar sin duplicar la pregunta', async () => {
    mockedAsk
      .mockRejectedValueOnce(new ApiError(503, { code: 'ai_unavailable', message: 'down' }))
      .mockResolvedValueOnce(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    await user.type(screen.getByLabelText('Tu pregunta'), '¿Roles?{Enter}');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('El asistente no está disponible');

    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await screen.findByText(/Cada servicio valida el JWT/);

    expect(mockedAsk).toHaveBeenCalledTimes(2);
    expect(mockedAsk).toHaveBeenLastCalledWith(
      expect.objectContaining({ question: '¿Roles?', history: [] }),
    );
    expect(screen.getAllByText('¿Roles?')).toHaveLength(1);
  });

  it('avisa cuando la respuesta no supera la validación de calidad', async () => {
    mockedAsk.mockResolvedValue(
      makeAssistantAnswer({
        sources: [],
        quality: { passed: false, issues: ['missing_sources'] },
      }),
    );
    const { user } = renderApp('/assistant');

    await user.type(screen.getByLabelText('Tu pregunta'), '¿Sin contexto?{Enter}');

    const note = await screen.findByRole('note');
    expect(note).toHaveTextContent('no se han encontrado fuentes');
    expect(screen.queryByRole('heading', { name: 'Fuentes' })).not.toBeInTheDocument();
  });

  it('limpia la conversación con Nueva conversación', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    await user.type(screen.getByLabelText('Tu pregunta'), '¿Roles?{Enter}');
    await screen.findByText(/Cada servicio valida el JWT/);
    await user.click(screen.getByRole('button', { name: 'Nueva conversación' }));

    expect(screen.getByText('¿Qué quieres saber?')).toBeInTheDocument();
    expect(screen.queryByText('Tú')).not.toBeInTheDocument();
  });

  it('no permite enviar espacios en blanco', async () => {
    const { user } = renderApp('/assistant');

    await user.type(screen.getByLabelText('Tu pregunta'), '   ');
    await user.click(screen.getByRole('button', { name: 'Preguntar' }));

    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it('deniega el acceso sin el scope ai:use', async () => {
    signIn({ ...ADMIN, scopes: ADMIN.scopes.filter((scope) => scope !== 'ai:use') });
    renderApp('/assistant');

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeInTheDocument();
    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it('permite al admin reindexar la documentación desde la UI', async () => {
    mockedReindex.mockResolvedValue(REPORT);
    const { user } = renderApp('/assistant');

    await user.click(screen.getByRole('button', { name: 'Reindexar documentación' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Reindexar documentación' });
    await user.click(within(dialog).getByRole('button', { name: 'Reindexar' }));

    expect(await screen.findByText(/2 documentos y 20 fragmentos/)).toBeInTheDocument();
    expect(screen.getByText(/2 documentos, 20 fragmentos/)).toBeInTheDocument();
    expect(mockedReindex).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('no reindexa si el admin cancela la confirmación', async () => {
    const { user } = renderApp('/assistant');

    await user.click(screen.getByRole('button', { name: 'Reindexar documentación' }));
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(mockedReindex).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('oculta la reindexación a los usuarios que no son admin', async () => {
    signIn(AI_READER);
    renderApp('/assistant');

    expect(
      screen.queryByRole('button', { name: 'Reindexar documentación' }),
    ).not.toBeInTheDocument();
  });

  it('muestra el error de reindexación sin cerrar la conversación', async () => {
    mockedReindex.mockRejectedValue(new ApiError(503, { code: 'ai_unavailable', message: 'down' }));
    const { user } = renderApp('/assistant');

    await user.click(screen.getByRole('button', { name: 'Reindexar documentación' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Reindexar documentación' });
    await user.click(within(dialog).getByRole('button', { name: 'Reindexar' }));

    const alerts = await screen.findAllByText(/no está disponible ahora mismo/);
    expect(alerts.length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Asistente' })).toBeInTheDocument();
  });

  it('muestra el autor y las fuentes dentro del mensaje del asistente', async () => {
    mockedAsk.mockResolvedValue(makeAssistantAnswer());
    const { user } = renderApp('/assistant');

    await user.type(screen.getByLabelText('Tu pregunta'), '¿Tokens?{Enter}');
    await screen.findByText(/Cada servicio valida el JWT/);

    const answer = screen.getByRole('article', { name: 'Respuesta del asistente' });
    expect(within(answer).getByText(/Validación de tokens/)).toBeInTheDocument();
    expect(within(answer).getByText('prompt v1')).toBeInTheDocument();
  });
});
