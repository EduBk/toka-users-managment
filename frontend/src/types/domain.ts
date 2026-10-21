export interface SessionUser {
  id: string;
  email: string;
  roles: string[];
  scopes: string[];
}

export type UserStatus = 'active' | 'inactive';

export interface User {
  id: string;
  email: string;
  name: string;
  status: UserStatus;
  profile: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  created_at: string;
  updated_at: string;
}

export interface Account {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface AuditEntry {
  event_id: string;
  type: string;
  version: number;
  occurred_at: string;
  producer: string;
  actor_id: string | null;
  payload: Record<string, unknown>;
  correlation_id: string;
}

export interface AssistantSource {
  document: string;
  section: string;
  score: number;
}

export interface AssistantUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface AssistantLatency {
  total_ms: number;
  embedding_ms: number;
  retrieval_ms: number;
  llm_ms: number;
}

export interface AssistantQuality {
  passed: boolean;
  issues: string[];
}

export interface AssistantAnswer {
  answer: string;
  sources: AssistantSource[];
  usage: AssistantUsage;
  latency: AssistantLatency;
  model: string;
  prompt_version: string;
  quality: AssistantQuality;
}
