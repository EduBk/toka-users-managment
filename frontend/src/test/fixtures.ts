import type { AssistantAnswer, AuditEntry, Role, User } from '@/types/domain';

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    email: 'ana@example.com',
    name: 'Ana Pérez',
    status: 'active',
    profile: {},
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    ...overrides,
  };
}

export function makeRole(overrides: Partial<Role> = {}): Role {
  return {
    id: '00000000-0000-4000-8000-000000000001',
    name: 'admin',
    description: 'System administrator',
    permissions: ['users:read', 'users:write'],
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    ...overrides,
  };
}

export function makeAuditEntry(overrides: Partial<AuditEntry> = {}): AuditEntry {
  return {
    event_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    type: 'user.created',
    version: 1,
    occurred_at: '2026-10-20T09:30:00Z',
    producer: 'user-service',
    actor_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    payload: { user_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' },
    correlation_id: 'trace-123456',
    ...overrides,
  };
}

export function page<T>(items: T[], total = items.length, pageNumber = 1, pageSize = 20) {
  return { items, total, page: pageNumber, page_size: pageSize };
}

export function makeAssistantAnswer(overrides: Partial<AssistantAnswer> = {}): AssistantAnswer {
  return {
    answer: 'Cada servicio valida el JWT localmente con el JWKS de auth-service [1].',
    sources: [
      {
        document: 'arquitectura/flujos-de-datos.md',
        section: 'Validación de tokens',
        score: 0.83,
      },
    ],
    usage: { input_tokens: 27, output_tokens: 8, total_tokens: 35, cost_usd: 0.000334 },
    latency: { total_ms: 1250.5, embedding_ms: 210.2, retrieval_ms: 32.1, llm_ms: 1008.2 },
    model: 'gpt-4o-mini',
    prompt_version: 'v1',
    quality: { passed: true, issues: [] },
    ...overrides,
  };
}
