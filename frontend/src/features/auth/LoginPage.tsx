import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { Brand } from '@/components/Brand';
import { validateEmail } from '@/services/validation';
import { useAuthStore } from '@/stores/authStore';

import './LoginPage.css';

interface FieldErrors {
  email?: string;
  password?: string;
}

function validate(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  const emailError = validateEmail(email);
  if (emailError) errors.email = emailError;
  if (!password) errors.password = 'Introduce tu contraseña.';
  return errors;
}

export function LoginPage() {
  const { user, status, error, sessionExpired, login } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const from = (location.state as { from?: string } | null)?.from ?? '/';
  const loading = status === 'loading';

  if (user) return <Navigate to={from} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validate(email.trim(), password);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    if (await login(email.trim(), password)) navigate(from, { replace: true });
  }

  return (
    <div className="login">
      <aside className="login__aside">
        <div className="login__brand">
          <Brand inverse size={34} />
        </div>
        <div className="login__pitch">
          <h1>Accesos, roles y auditoría en un solo lugar.</h1>
          <p>Administra quién entra, qué puede hacer y deja registro de cada movimiento.</p>
        </div>
      </aside>
      <div className="login__form-wrap">
        <form
          className="login__form"
          onSubmit={handleSubmit}
          noValidate
          aria-label="Iniciar sesión"
        >
          <div className="login__intro">
            <h2>Iniciar sesión</h2>
            <p className="muted">Entra con tu cuenta corporativa.</p>
          </div>
          {sessionExpired && !error && (
            <p className="alert alert--info" role="status">
              Tu sesión ha caducado. Inicia sesión de nuevo.
            </p>
          )}
          {error && (
            <p className="alert" role="alert">
              {error}
            </p>
          )}
          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
              disabled={loading}
            />
            {fieldErrors.email && <span className="field__error">{fieldErrors.email}</span>}
          </label>
          <label className="field">
            <span className="field__label">Contraseña</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={Boolean(fieldErrors.password)}
              disabled={loading}
            />
            {fieldErrors.password && <span className="field__error">{fieldErrors.password}</span>}
          </label>
          <button className="button" type="submit" disabled={loading}>
            {loading ? 'Iniciando sesión…' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  );
}
