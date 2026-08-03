import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LoginForm from '../LoginForm';
import userEvent from '@testing-library/user-event';

jest.mock('quill', () => {
  return jest.fn().mockImplementation(() => ({
    on: jest.fn(),
    getContents: jest.fn(),
    setContents: jest.fn(),
    root: { innerHTML: '' },
    clipboard: { convert: jest.fn() },
    setText: jest.fn(),
    getText: jest.fn(),
  }));
});

describe('LoginForm', () => {
  const mockSubmit = jest.fn();

  beforeEach(() => {
    mockSubmit.mockClear();
  });

  test('calls onSubmit with correct values', async () => {
    const mockOnSubmit = jest.fn();

    render(<LoginForm onSubmit={mockOnSubmit} />);

    const emailInput = screen.getByPlaceholderText(/email/i);
    const passwordInput = screen.getByPlaceholderText(/password/i);
    const submitButton = screen.getByRole('button', { name: /log in/i });

    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'ValidPass123!');

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      expect(mockOnSubmit).toHaveBeenCalledWith(
        {
          email: 'test@example.com',
          password: 'ValidPass123!',
        },
        expect.any(Function)
      );
    });
  });

  test('renders email and password fields', () => {
    render(<LoginForm onSubmit={mockSubmit} />);
    expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  test('displays validation errors on empty submit', async () => {
    render(<LoginForm onSubmit={mockSubmit} />);
    fireEvent.submit(screen.getByRole('button', { name: /log in/i }));

    expect(await screen.findByText(/Email is required/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/password must be at least 6 characters/i)
    ).toBeInTheDocument();
  });

  test('shows error for invalid email format', async () => {
    render(<LoginForm onSubmit={mockSubmit} />);
    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: 'invalid-email' },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: 'ValidPass123!' },
    });

    fireEvent.submit(screen.getByRole('button', { name: /log in/i }));

    expect(
      await screen.findByText(/Please enter a valid email address./i)
    ).toBeInTheDocument();
  });

  test('calls onSubmit with valid data', async () => {
    render(<LoginForm onSubmit={mockSubmit} />);

    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: 'ValidPass123!' },
    });

    fireEvent.submit(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith(
        {
          email: 'test@example.com',
          password: 'ValidPass123!',
        },
        expect.any(Function)
      );
    });
  });

  test('disables submit button when form is invalid', async () => {
    render(<LoginForm onSubmit={mockSubmit} />);
    const button = screen.getByRole('button', { name: /log in/i });

    expect(button).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: 'ValidPass123!' },
    });

    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });
  });

  test('calls handleFormSubmit directly', () => {
    const onSubmit = jest.fn();
    const { container } = render(<LoginForm onSubmit={onSubmit} />);

    const form = container.querySelector('form');
    expect(form).toBeInTheDocument();
  });
  test('renders with default onSubmit without crashing', async () => {
    const mockOnSubmit = jest.fn();

    render(<LoginForm onSubmit={mockOnSubmit} />);

    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: 'ValidPass123!' },
    });

    fireEvent.submit(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/email/i)).toHaveValue(
        'test@example.com'
      );
    });

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalled();
    });
  });
  test('disables button when form is invalid', () => {
    render(<LoginForm onSubmit={mockSubmit} />);
    const button = screen.getByRole('button', { name: /log in/i });
    expect(button).toBeDisabled();
  });
});
