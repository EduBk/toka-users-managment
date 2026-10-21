import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';

import { ConfirmDialog } from '@/components/ConfirmDialog';
import { EmptyState, ErrorState, Spinner } from '@/components/feedback';
import { ACCESS, hasAccess } from '@/features/auth/access';
import { useAssistantStore, type AssistantMessage } from '@/stores/assistantStore';
import { useAuthStore } from '@/stores/authStore';
import { notify } from '@/stores/toastStore';
import type { AssistantAnswer } from '@/types/domain';

import './AssistantPage.css';

export const MAX_QUESTION_LENGTH = 2000;

const SUGGESTIONS = [
  '¿Qué microservicios forman el sistema?',
  '¿Cómo se validan los tokens JWT entre microservicios?',
  '¿Qué eventos de dominio se publican en RabbitMQ?',
];

const QUALITY_ISSUES: Record<string, string> = {
  missing_sources: 'no se han encontrado fuentes',
  answer_too_long: 'la respuesta es demasiado larga',
  pii_in_answer: 'se han redactado datos personales',
  empty_answer: 'la respuesta llegó vacía',
};

const numberFormat = new Intl.NumberFormat('es');
const costFormat = new Intl.NumberFormat('es', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 6,
});

function qualityWarning(answer: AssistantAnswer): string {
  const issues = answer.quality.issues.map((issue) => QUALITY_ISSUES[issue] ?? issue);
  return `Respuesta a revisar: ${issues.join(', ')}.`;
}

function AnswerDetails({ answer }: { answer: AssistantAnswer }) {
  return (
    <>
      {answer.sources.length > 0 && (
        <div className="assistant__sources">
          <h3>Fuentes</h3>
          <ul>
            {answer.sources.map((source, index) => (
              <li key={`${source.document}-${source.section}-${index}`}>
                <span className="assistant__source-index">[{index + 1}]</span>{' '}
                <code>{source.document}</code> — {source.section}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!answer.quality.passed && (
        <p className="assistant__warning" role="note">
          {qualityWarning(answer)}
        </p>
      )}
      <p className="assistant__meta">
        <span>{numberFormat.format(answer.latency.total_ms)} ms</span>
        <span>{numberFormat.format(answer.usage.total_tokens)} tokens</span>
        <span>{costFormat.format(answer.usage.cost_usd)}</span>
        <span>prompt {answer.prompt_version}</span>
        <span>{answer.model}</span>
      </p>
    </>
  );
}

function Message({ message }: { message: AssistantMessage }) {
  const author = message.role === 'user' ? 'Tú' : 'Asistente';
  return (
    <article
      className={`assistant__message assistant__message--${message.role}`}
      aria-label={message.role === 'user' ? 'Pregunta enviada' : 'Respuesta del asistente'}
    >
      <p className="assistant__author">{author}</p>
      <p className="assistant__text">{message.content}</p>
      {message.answer && <AnswerDetails answer={message.answer} />}
    </article>
  );
}

export function AssistantPage() {
  const user = useAuthStore((state) => state.user);
  const messages = useAssistantStore((state) => state.messages);
  const status = useAssistantStore((state) => state.status);
  const error = useAssistantStore((state) => state.error);
  const includeSystemData = useAssistantStore((state) => state.includeSystemData);
  const ask = useAssistantStore((state) => state.ask);
  const retry = useAssistantStore((state) => state.retry);
  const reset = useAssistantStore((state) => state.reset);
  const setIncludeSystemData = useAssistantStore((state) => state.setIncludeSystemData);
  const reindexStatus = useAssistantStore((state) => state.reindexStatus);
  const reindexResult = useAssistantStore((state) => state.reindexResult);
  const reindexError = useAssistantStore((state) => state.reindexError);
  const reindex = useAssistantStore((state) => state.reindex);

  const [question, setQuestion] = useState('');
  const [confirmReindex, setConfirmReindex] = useState(false);
  const bottomRef = useRef<HTMLLIElement>(null);
  const loading = status === 'loading';
  const canIncludeSystemData = hasAccess(user, ACCESS.usersRead);
  const canReindex = hasAccess(user, ACCESS.rolesAdmin);
  const canSubmit =
    question.trim().length > 0 && question.length <= MAX_QUESTION_LENGTH && !loading;

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages.length, status]);

  function send() {
    if (!canSubmit) return;
    void ask(question);
    setQuestion('');
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    send();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  async function handleReindex() {
    const result = await reindex();
    setConfirmReindex(false);
    if (result) {
      notify.success(
        `Documentación indexada: ${result.documents_indexed} documentos, ${result.chunks_indexed} fragmentos.`,
      );
    } else {
      notify.error(
        useAssistantStore.getState().reindexError ?? 'No se pudo reindexar la documentación.',
      );
    }
  }

  return (
    <section className="assistant">
      <div className="page-header">
        <div>
          <h1>Asistente</h1>
          <p className="muted">
            Pregunta sobre la documentación y los datos del sistema. Las respuestas citan las
            fuentes consultadas.
          </p>
        </div>
        <div className="assistant__header-actions">
          {canReindex && (
            <button
              type="button"
              className="button button--secondary button--small"
              onClick={() => setConfirmReindex(true)}
              disabled={reindexStatus === 'loading'}
            >
              {reindexStatus === 'loading' ? 'Indexando…' : 'Reindexar documentación'}
            </button>
          )}
          <button
            type="button"
            className="button button--secondary button--small"
            onClick={reset}
            disabled={messages.length === 0 || loading}
          >
            Nueva conversación
          </button>
        </div>
      </div>

      {reindexStatus === 'loading' && (
        <p className="assistant__hint" role="status">
          <Spinner label="Indexando la documentación…" />
        </p>
      )}
      {reindexStatus === 'error' && reindexError && (
        <p className="assistant__reindex assistant__reindex--error" role="alert">
          {reindexError}
        </p>
      )}
      {reindexResult && (
        <p className="assistant__reindex" role="status">
          Documentación indexada: {reindexResult.documents_indexed} documentos y{' '}
          {reindexResult.chunks_indexed} fragmentos
          {reindexResult.documents_skipped > 0 &&
            ` · ${reindexResult.documents_skipped} sin cambios`}
          {reindexResult.documents_deleted > 0 &&
            ` · ${reindexResult.documents_deleted} eliminados`}
          .
        </p>
      )}

      {messages.length === 0 && (
        <EmptyState
          title="¿Qué quieres saber?"
          description="El asistente busca en la documentación del repositorio y responde citando los fragmentos que ha usado."
          action={
            <ul className="assistant__suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    className="button button--secondary button--small"
                    onClick={() => void ask(suggestion)}
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          }
        />
      )}

      {messages.length > 0 && (
        <ol
          className="assistant__log"
          aria-label="Conversación"
          role="log"
          aria-relevant="additions"
        >
          {messages.map((message) => (
            <li key={message.id} className={`assistant__item assistant__item--${message.role}`}>
              <Message message={message} />
            </li>
          ))}
          {loading && (
            <li className="assistant__item">
              <span className="assistant__thinking">
                <Spinner label="Consultando la documentación…" />
              </span>
            </li>
          )}
          <li ref={bottomRef} aria-hidden="true" />
        </ol>
      )}

      {status === 'error' && (
        <ErrorState
          message={error ?? 'No se pudo obtener la respuesta del asistente.'}
          onRetry={() => void retry()}
        />
      )}

      <form className="assistant__composer" onSubmit={handleSubmit}>
        <label className="field__label" htmlFor="assistant-question">
          Tu pregunta
        </label>
        <div className="assistant__composer-row">
          <textarea
            id="assistant-question"
            className="input assistant__textarea"
            rows={3}
            value={question}
            maxLength={MAX_QUESTION_LENGTH}
            placeholder="Ej.: ¿Cómo se validan los tokens entre microservicios?"
            disabled={loading}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button type="submit" className="button" disabled={!canSubmit}>
            {loading ? 'Consultando…' : 'Preguntar'}
          </button>
        </div>
        <div className="assistant__options">
          <p className="assistant__hint">
            Intro envía · Mayús+Intro salto de línea · {question.length}/{MAX_QUESTION_LENGTH}
          </p>
          {canIncludeSystemData && (
            <label className="assistant__toggle">
              <input
                type="checkbox"
                checked={includeSystemData}
                disabled={loading}
                onChange={(event) => setIncludeSystemData(event.target.checked)}
              />
              Incluir datos del sistema (usuarios y roles)
            </label>
          )}
        </div>
      </form>

      {confirmReindex && (
        <ConfirmDialog
          title="Reindexar documentación"
          message="Se indexarán los documentos de docs/ en Qdrant. Solo se procesan los archivos nuevos o modificados; la primera vez puede tardar varios minutos mientras se descarga el modelo de embeddings."
          confirmLabel="Reindexar"
          busy={reindexStatus === 'loading'}
          onConfirm={() => void handleReindex()}
          onCancel={() => setConfirmReindex(false)}
        />
      )}
    </section>
  );
}
