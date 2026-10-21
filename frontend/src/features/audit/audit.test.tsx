import { screen, within } from '@testing-library/react';

import { ApiError } from '@/services/apiClient';
import { auditApi } from '@/services/auditApi';
import { useAuditStore } from '@/stores/auditStore';
import { makeAuditEntry, page } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { ADMIN, signIn } from '@/test/session';

jest.mock('@/services/auditApi', () => ({ auditApi: { search: jest.fn() } }));

const mockedSearch = jest.mocked(auditApi.search);
const AUDITOR = { ...ADMIN, roles: ['auditor'], scopes: ['audit:read'] };
const created = makeAuditEntry();
const login = makeAuditEntry({
  event_id: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
  type: 'user.logged_in',
  producer: 'auth-service',
  payload: { user_id: 'acc-1', email: 'ana@example.com' },
});

beforeEach(() => {
  jest.resetAllMocks();
  useAuditStore.setState({ filters: {}, page: 1, status: 'idle', items: [], total: 0 });
  signIn(AUDITOR);
});

describe('vista de auditoría', () => {
  it('lista los eventos paginados para un auditor', async () => {
    mockedSearch.mockResolvedValue(page([created, login], 45));
    renderApp('/audit');

    const table = await screen.findByRole('table');
    expect(within(table).getByText('user.created')).toBeInTheDocument();
    expect(within(table).getByText('auth-service')).toBeInTheDocument();
    expect(screen.getByText('Página 1 de 3 (45 eventos)')).toBeInTheDocument();
    expect(mockedSearch).toHaveBeenCalledWith({}, 1, 20);
  });

  it('aplica filtros y pagina sin recargar', async () => {
    mockedSearch.mockResolvedValue(page([login], 45));
    const { user } = renderApp('/audit');
    await screen.findByRole('table');

    await user.type(screen.getByLabelText('Usuario (ID)'), ' acc-1 ');
    await user.selectOptions(screen.getByLabelText('Tipo de evento'), 'user.logged_in');
    await user.type(screen.getByLabelText('Desde'), '2026-10-01');
    await user.type(screen.getByLabelText('Hasta'), '2026-10-20');
    await user.click(screen.getByRole('button', { name: 'Aplicar filtros' }));
    await screen.findByRole('table');

    const filters = {
      user: 'acc-1',
      type: 'user.logged_in',
      from: new Date('2026-10-01T00:00:00').toISOString(),
      to: new Date('2026-10-20T23:59:59.999').toISOString(),
    };
    expect(mockedSearch).toHaveBeenLastCalledWith(filters, 1, 20);

    await user.click(screen.getByRole('button', { name: 'Siguiente' }));
    await screen.findByRole('table');
    expect(mockedSearch).toHaveBeenLastCalledWith(filters, 2, 20);

    await user.click(screen.getByRole('button', { name: 'Limpiar' }));
    expect(mockedSearch).toHaveBeenLastCalledWith({}, 1, 20);
  });

  it('rechaza un rango de fechas invertido', async () => {
    mockedSearch.mockResolvedValue(page([created]));
    const { user } = renderApp('/audit');
    await screen.findByRole('table');

    await user.type(screen.getByLabelText('Desde'), '2026-10-20');
    await user.type(screen.getByLabelText('Hasta'), '2026-10-01');
    await user.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    expect(screen.getByRole('alert')).toHaveTextContent('no puede ser posterior');
    expect(mockedSearch).toHaveBeenCalledTimes(1);
  });

  it('muestra el detalle del evento con payload, correlation_id y productor', async () => {
    mockedSearch.mockResolvedValue(page([login]));
    const { user } = renderApp('/audit');

    await user.click(await screen.findByRole('button', { name: 'Ver detalle de user.logged_in' }));

    const dialog = screen.getByRole('dialog', { name: 'user.logged_in' });
    expect(within(dialog).getByText('trace-123456')).toBeInTheDocument();
    expect(within(dialog).getByText('auth-service')).toBeInTheDocument();
    expect(within(dialog).getByText(/"email": "ana@example.com"/)).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('muestra estado vacío y error con reintento', async () => {
    mockedSearch
      .mockRejectedValueOnce(new ApiError(503, { code: 'service_unavailable', message: 'x' }))
      .mockResolvedValueOnce(page([]));
    const { user } = renderApp('/audit');

    await user.click(await screen.findByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('Sin eventos')).toBeInTheDocument();
  });

  it('deniega el acceso a usuarios sin rol auditor ni admin', async () => {
    signIn({ ...ADMIN, roles: ['editor'], scopes: ['users:read', 'audit:read'] });
    renderApp('/audit');

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeInTheDocument();
    expect(mockedSearch).not.toHaveBeenCalled();
  });
});
