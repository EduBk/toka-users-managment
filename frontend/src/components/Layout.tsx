import { useState } from 'react';
import { ScrollText, ShieldCheck, Sparkles, Users, type LucideIcon } from 'lucide-react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { Brand } from '@/components/Brand';
import { Toaster } from '@/components/Toaster';
import { Button } from '@/components/ui/button';
import { ACCESS, hasAccess, type AccessRule } from '@/features/auth/access';
import { useAuthStore } from '@/stores/authStore';

import './Layout.css';

interface NavItem {
  to: string;
  label: string;
  rule: AccessRule;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/users', label: 'Usuarios', rule: ACCESS.usersRead, icon: Users },
  { to: '/roles', label: 'Roles', rule: ACCESS.rolesAdmin, icon: ShieldCheck },
  { to: '/audit', label: 'Auditoría', rule: ACCESS.audit, icon: ScrollText },
  { to: '/assistant', label: 'Asistente', rule: ACCESS.aiUse, icon: Sparkles },
];

function initials(email: string | undefined): string {
  const local = (email ?? '').split('@')[0] ?? '';
  return local.slice(0, 2).toUpperCase() || '—';
}

export function Layout() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  async function handleLogout() {
    setSigningOut(true);
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="layout">
      <header className="layout__bar">
        <div className="layout__bar-inner">
          <Link className="layout__brand" to="/users" aria-label="Toka, ir a usuarios">
            <Brand inverse size={30} />
          </Link>
          <nav className="layout__nav" aria-label="Principal">
            {NAV_ITEMS.filter((item) => hasAccess(user, item.rule)).map((item) => {
              const Icon = item.icon;
              return (
                <NavLink key={item.to} to={item.to} className="layout__nav-link">
                  <Icon className="layout__nav-icon" aria-hidden="true" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
          {user && (
            <div className="layout__session">
              <span className="layout__avatar" aria-hidden="true">
                {initials(user.email)}
              </span>
              <div className="layout__user">
                <span className="layout__user-email">{user.email}</span>
                <span className="layout__user-roles">{user.roles.join(' · ') || 'Sin roles'}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={handleLogout}
                disabled={signingOut}
                className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white"
              >
                {signingOut ? 'Cerrando sesión…' : 'Cerrar sesión'}
              </Button>
            </div>
          )}
        </div>
      </header>
      <main className="layout__content">
        <Outlet />
      </main>
      <Toaster />
    </div>
  );
}
