export function PermissionChips({ permissions }: { permissions: string[] }) {
  if (permissions.length === 0) return <span className="muted">Sin permisos</span>;
  return (
    <ul className="chips" aria-label="Permisos">
      {permissions.map((permission) => {
        const [resource, ...rest] = permission.split(':');
        return (
          <li key={permission} className="chip">
            <span className="chip__resource">{resource}</span>
            {rest.length > 0 && <span className="chip__action">:{rest.join(':')}</span>}
          </li>
        );
      })}
    </ul>
  );
}

interface PermissionPickerProps {
  catalog: string[];
  value: string[];
  disabled?: boolean;
  onChange: (permissions: string[]) => void;
}

export function PermissionPicker({ catalog, value, disabled, onChange }: PermissionPickerProps) {
  function toggle(permission: string, checked: boolean) {
    onChange(checked ? [...value, permission].sort() : value.filter((item) => item !== permission));
  }

  return (
    <fieldset className="permission-picker" disabled={disabled}>
      <legend className="field__label">Permisos</legend>
      {catalog.map((permission) => (
        <label key={permission} className="permission-picker__option">
          <input
            type="checkbox"
            checked={value.includes(permission)}
            onChange={(event) => toggle(permission, event.target.checked)}
          />
          <code>{permission}</code>
        </label>
      ))}
    </fieldset>
  );
}
