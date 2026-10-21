import { useState, type FormEvent } from 'react';

import { PermissionPicker } from '@/features/roles/PermissionControls';
import type { RoleInput } from '@/services/rolesApi';
import { validateRoleName } from '@/services/validation';

interface RoleCreateFormProps {
  catalog: string[];
  busy: boolean;
  error: string | null;
  onSubmit: (input: RoleInput) => void;
  onCancel: () => void;
}

export function RoleCreateForm({ catalog, busy, error, onSubmit, onCancel }: RoleCreateFormProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [permissions, setPermissions] = useState<string[]>([]);
  const [nameError, setNameError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = name.trim().toLowerCase();
    const validation = validateRoleName(normalized);
    setNameError(validation);
    if (!validation) onSubmit({ name: normalized, description: description.trim(), permissions });
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate aria-label="Nuevo rol">
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
          aria-invalid={Boolean(nameError)}
          maxLength={60}
          disabled={busy}
        />
        {nameError && <span className="field__error">{nameError}</span>}
      </label>
      <label className="field">
        <span className="field__label">Descripción</span>
        <input
          className="input"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={255}
          disabled={busy}
        />
      </label>
      <PermissionPicker
        catalog={catalog}
        value={permissions}
        disabled={busy}
        onChange={setPermissions}
      />
      <div className="form__actions">
        <button className="button" type="submit" disabled={busy}>
          {busy ? 'Creando…' : 'Crear rol'}
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
