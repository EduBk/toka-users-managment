import { Navigate, type RouteObject } from 'react-router-dom';

import { NotFoundPage } from '@/app/NotFoundPage';
import { Layout } from '@/components/Layout';
import { AssistantPage } from '@/features/ai/AssistantPage';
import { AuditPage } from '@/features/audit/AuditPage';
import { ACCESS } from '@/features/auth/access';
import { RequireAccess, RequireAuth } from '@/features/auth/guards';
import { LoginPage } from '@/features/auth/LoginPage';
import { RolesPage } from '@/features/roles/RolesPage';
import { UserCreatePage } from '@/features/users/UserCreatePage';
import { UserDetailPage } from '@/features/users/UserDetailPage';
import { UsersPage } from '@/features/users/UsersPage';

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/users" replace /> },
      {
        path: 'users',
        element: (
          <RequireAccess rule={ACCESS.usersRead}>
            <UsersPage />
          </RequireAccess>
        ),
      },
      {
        path: 'users/new',
        element: (
          <RequireAccess rule={ACCESS.usersWrite}>
            <UserCreatePage />
          </RequireAccess>
        ),
      },
      {
        path: 'users/:userId',
        element: (
          <RequireAccess rule={ACCESS.usersRead}>
            <UserDetailPage />
          </RequireAccess>
        ),
      },
      {
        path: 'roles',
        element: (
          <RequireAccess rule={ACCESS.rolesAdmin}>
            <RolesPage />
          </RequireAccess>
        ),
      },
      {
        path: 'audit',
        element: (
          <RequireAccess rule={ACCESS.audit}>
            <AuditPage />
          </RequireAccess>
        ),
      },
      {
        path: 'assistant',
        element: (
          <RequireAccess rule={ACCESS.aiUse}>
            <AssistantPage />
          </RequireAccess>
        ),
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
];
