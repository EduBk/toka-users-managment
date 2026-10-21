import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ConfirmDialog } from '@/components/ConfirmDialog';
import { EmptyState, ErrorState, Skeleton, Spinner } from '@/components/feedback';
import { Toaster } from '@/components/Toaster';
import { notify, useToastStore } from '@/stores/toastStore';

describe('componentes de feedback', () => {
  it('Spinner y Skeleton anuncian la carga', () => {
    render(
      <>
        <Spinner label="Guardando" />
        <Skeleton rows={2} label="Cargando tabla" />
      </>,
    );

    expect(screen.getByText('Guardando')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Cargando tabla' })).toBeInTheDocument();
  });

  it('ErrorState muestra el mensaje y reintenta', async () => {
    const onRetry = jest.fn();
    render(<ErrorState message="Falló la carga" onRetry={onRetry} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Falló la carga');
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('EmptyState muestra título, descripción y acción', () => {
    render(
      <EmptyState title="Nada aquí" description="Crea algo" action={<button>Crear</button>} />,
    );

    expect(screen.getByRole('heading', { name: 'Nada aquí' })).toBeInTheDocument();
    expect(screen.getByText('Crea algo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear' })).toBeInTheDocument();
  });

  it('ConfirmDialog enfoca cancelar, se cierra con Escape y bloquea botones ocupado', async () => {
    const onCancel = jest.fn();
    const { rerender } = render(
      <ConfirmDialog
        title="¿Seguro?"
        message="No hay vuelta atrás"
        confirmLabel="Borrar"
        onConfirm={jest.fn()}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();

    rerender(
      <ConfirmDialog
        title="¿Seguro?"
        message="No hay vuelta atrás"
        confirmLabel="Borrar"
        busy
        onConfirm={jest.fn()}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByRole('button', { name: 'Procesando…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
  });
});

describe('toasts', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    useToastStore.setState({ toasts: [] });
  });

  afterEach(() => jest.useRealTimers());

  it('muestra éxito y error y desaparecen solos', () => {
    render(<Toaster />);

    act(() => {
      notify.success('Guardado.');
      notify.error('Falló.');
    });

    expect(screen.getByRole('status')).toHaveTextContent('Guardado.');
    expect(screen.getByRole('alert')).toHaveTextContent('Falló.');

    act(() => jest.advanceTimersByTime(5000));

    expect(screen.queryByText('Guardado.')).not.toBeInTheDocument();
    expect(screen.queryByText('Falló.')).not.toBeInTheDocument();
  });

  it('se pueden cerrar manualmente', async () => {
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    render(<Toaster />);
    act(() => notify.success('Hecho.'));

    await user.click(screen.getByRole('button', { name: 'Cerrar notificación' }));

    expect(screen.queryByText('Hecho.')).not.toBeInTheDocument();
  });
});
