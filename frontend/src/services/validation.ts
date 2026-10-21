const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MAX_EMAIL_LENGTH = 254;
const MAX_NAME_LENGTH = 120;

export function validateEmail(email: string): string | null {
  if (!email) return 'Introduce un email.';
  if (email.length > MAX_EMAIL_LENGTH || !EMAIL_PATTERN.test(email)) {
    return 'Introduce un email válido.';
  }
  return null;
}

const ROLE_NAME_PATTERN = /^[a-z0-9][a-z0-9_-]*$/;
const MAX_ROLE_NAME_LENGTH = 60;

export function validateRoleName(name: string): string | null {
  if (!name) return 'Introduce un nombre.';
  if (name.length > MAX_ROLE_NAME_LENGTH || !ROLE_NAME_PATTERN.test(name)) {
    return 'Usa hasta 60 letras minúsculas, números, guiones o guiones bajos.';
  }
  return null;
}

export function validateName(name: string): string | null {
  if (!name) return 'Introduce un nombre.';
  if (name.length > MAX_NAME_LENGTH)
    return `El nombre admite como máximo ${MAX_NAME_LENGTH} caracteres.`;
  return null;
}
