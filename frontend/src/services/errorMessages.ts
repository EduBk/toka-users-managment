import { ApiError } from '@/services/apiClient';

const MESSAGES: Record<string, string> = {
  email_already_exists: 'Ya existe un usuario con ese email.',
  invalid_email: 'El email no es válido.',
  invalid_name: 'El nombre no es válido.',
  invalid_profile: 'El perfil no es válido.',
  invalid_user_state: 'El usuario está desactivado y no se puede modificar.',
  user_not_found: 'El usuario no existe.',
  account_not_found: 'No hay ninguna cuenta registrada con ese email.',
  role_not_found: 'El rol no existe.',
  role_already_exists: 'Ya existe un rol con ese nombre.',
  invalid_role_name: 'El nombre del rol no es válido.',
  invalid_role_description: 'La descripción del rol no es válida.',
  invalid_permission_name: 'Algún permiso no tiene un formato válido.',
  insufficient_scope: 'No tienes permisos para realizar esta acción.',
  insufficient_role: 'No tienes permisos para realizar esta acción.',
  forbidden: 'No tienes permisos para realizar esta acción.',
  validation_error: 'Revisa los datos enviados: alguno no tiene un formato válido.',
  internal_error: 'Error interno del servidor. Inténtalo de nuevo más tarde.',
  service_unavailable: 'El servicio no está disponible. Inténtalo de nuevo más tarde.',
  ai_unavailable:
    'El asistente no está disponible ahora mismo. Inténtalo de nuevo en unos minutos.',
  ai_not_configured:
    'La API key del proveedor de IA no es válida. Revisa OPENAI_API_KEY en el servidor.',
  ai_model_unavailable:
    'El modelo configurado no está disponible para esa cuenta. Revisa OPENAI_MODEL.',
  ai_rate_limited:
    'Has hecho demasiadas consultas seguidas. Espera un momento y vuelve a intentarlo.',
  rate_limited: 'Has hecho demasiadas consultas seguidas. Espera un momento y vuelve a intentarlo.',
  invalid_question: 'La pregunta no es válida. Escribe una consulta más concreta.',
  reindex_failed: 'No se pudo reindexar la documentación. Inténtalo de nuevo.',
  documentation_unavailable:
    'No se encontró la carpeta de documentación en el servidor. Revisa DOCS_PATH.',
};

export function errorMessage(error: unknown, fallback = 'Algo ha fallado.'): string {
  if (error instanceof ApiError) return MESSAGES[error.code] ?? error.message;
  return fallback;
}
