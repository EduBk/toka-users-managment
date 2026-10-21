import { useState, type FormEvent } from 'react';

import type { UserInput } from '@/services/usersApi';
import { validateEmail, validateName } from '@/services/validation';

interface UserFormProps {
  initial?: UserInput;
  submitLabel: string;
  busy: boolean;
  disabled?: boolean;
  error: string | null;
  onSubmit: (input: UserInput) => void;
  onCancel: () => void;
}

interface FieldErrors {
  email?: string;
  name?: string;
}

export function UserForm({
  initial = { email: '', name: '' },
  submitLabel,
  busy,
  disabled = false,
  error,
  onSubmit,
  onCancel,
}: UserFormProps) {
  const [email, setEmail] = useState(initial.email);
  const [name, setName] = useState(initial.name);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const locked = busy || disabled;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = { email: email.trim(), name: name.trim() };
    const errors: FieldErrors = {};
    const emailError = validateEmail(input.email);
    const nameError = validateName(input.name);
    if (emailError) errors.email = emailError;
    if (nameError) errors.name = nameError;
    setFieldErrors(errors);
    if (Object.keys(errors).length === 0) onSubmit(input);
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate aria-label="Datos del usuario">
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <label className="field">
        <span className="field__label">Nombre</span>
        <input
          className="input"
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-invalid={Boolean(fieldErrors.name)}
          maxLength={120}
          disabled={locked}
        />
        {fieldErrors.name && <span className="field__error">{fieldErrors.name}</span>}
      </label>
      <label className="field">
        <span className="field__label">Email</span>
        <input
          className="input"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
          maxLength={254}
          disabled={locked}
        />
        {fieldErrors.email && <span className="field__error">{fieldErrors.email}</span>}
      </label>
      <div className="form__actions">
        <button className="button" type="submit" disabled={locked}>
          {busy ? 'Guardando…' : submitLabel}
        </button>
        <button
          className="button button--secondary"
          type="button"
          onClick={onCancel}
          disabled={busy}
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}
