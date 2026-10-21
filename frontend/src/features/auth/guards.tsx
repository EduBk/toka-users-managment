import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { AccessDenied } from '@/components/AccessDenied';
import { hasAccess, type AccessRule } from '@/features/auth/access';
import { useAuthStore } from '@/stores/authStore';

export function RequireAuth({ children }: { children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export function RequireAccess({ rule, children }: { rule: AccessRule; children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  return hasAccess(user, rule) ? children : <AccessDenied />;
}
