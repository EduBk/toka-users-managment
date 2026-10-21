import { useState, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { Brand } from '@/components/Brand';
import { Toaster } from '@/components/Toaster';
import { ACCESS, hasAccess } from '@/features/auth/access';
import { useAuthStore } from '@/stores/authStore';

import './Layout.css';

function navIcon(children: ReactNode) {
  return (
    <svg
      className="layout__nav-icon"
      viewBox="0 0 18 18"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

const NAV_ITEMS = [
  {
    to: '/users',
    label: 'Usuarios',
    rule: ACCESS.usersRead,
    icon: navIcon(
      <>
        <circle cx="7" cy="6" r="2.6" />
        <path d="M2.5 15c0-2.6 2-4.4 4.5-4.4s4.5 1.8 4.5 4.4" />
        <path d="M12.2 4.2a2.4 2.4 0 0 1 0 4.6M13.5 14.6c0-1.6-.5-2.8-1.4-3.6" />
      </>,
    ),
  },
  {
    to: '/roles',
    label: 'Roles',
    rule: ACCESS.rolesAdmin,
    icon: navIcon(
      <>
        <path d="M9 1.8 15 4.2v4.4c0 3.5-2.4 6.3-6 7.6-3.6-1.3-6-4.1-6-7.6V4.2L9 1.8Z" />
        <path d="m6.7 8.8 1.6 1.6 3-3.2" />
      </>,
    ),
  },
  {
    to: '/audit',
    label: 'Auditoría',
    rule: ACCESS.audit,
    icon: navIcon(
      <>
        <path d="M2.5 4.5h13M2.5 9h13M2.5 13.5h8" />
        <circle cx="13.5" cy="13.5" r="1.6" />
      </>,
    ),
  },
  {
    to: '/assistant',
    label: 'Asistente',
    rule: ACCESS.aiUse,
    icon: navIcon(
      <>
        <path d="M9 2.5 10.4 6 14 7.4 10.4 8.8 9 12.3 7.6 8.8 4 7.4 7.6 6 9 2.5Z" />
        <path d="m14.2 12.3.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8Z" />
      </>,
    ),
  },
];

function initials(email: string | undefined): string {
  const local = (email ?? '').split('@')[0] ?? '';
  return local.slice(0, 2).toUpperCase() || '—';
}

export function Layout() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const location = useLocation();
  const [signingOut, setSigningOut] = useState(false);

  const currentSection =
    NAV_ITEMS.find((item) => location.pathname.startsWith(item.to))?.label ?? 'Inicio';

  async function handleLogout() {
    setSigningOut(true);
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="layout">
      <aside className="layout__sidebar">
        <div className="layout__brand">
          <Brand inverse size={30} />
        </div>
        <nav className="layout__nav" aria-label="Principal">
          {NAV_ITEMS.filter((item) => hasAccess(user, item.rule)).map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <p className="layout__sidebar-foot">Accesos, roles y auditoría en un solo lugar.</p>
      </aside>
      <div className="layout__main">
        <header className="layout__header">
          <span className="layout__section">{currentSection}</span>
          {user && (
            <div className="layout__session">
              <span className="layout__avatar" aria-hidden="true">
                {initials(user.email)}
              </span>
              <div className="layout__user">
                <span className="layout__user-email">{user.email}</span>
                <span className="layout__user-roles">{user.roles.join(' · ') || 'Sin roles'}</span>
              </div>
              <button
                className="button button--secondary button--small"
                type="button"
                onClick={handleLogout}
                disabled={signingOut}
              >
                {signingOut ? 'Cerrando sesión…' : 'Cerrar sesión'}
              </button>
            </div>
          )}
        </header>
        <main className="layout__content">
          <Outlet />
        </main>
      </div>
      <Toaster />
    </div>
  );
}
