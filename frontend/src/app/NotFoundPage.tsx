import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <main style={{ padding: 'var(--space-8)' }}>
      <h1>Página no encontrada</h1>
      <p>
        La dirección no existe. <Link to="/users">Ir a usuarios</Link>
      </p>
    </main>
  );
}
