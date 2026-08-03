import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { z } from 'zod';

import CloseIconMock from '../../../../__mocks__/CloseIcon.mock';
import * as authService from '@services/http/public/auth';
import MockPasswordField from '../../../UI/common/PasswordField/__mocks__/pwdField.mock';
import MockButtonCustomer from '../../../UI/customer/ButtonCustomer/__mocks__/ButtonCustomer.mock';
import { MockInputFieldCustomer } from '../../../UI/customer/InputFieldCustomer/__mocks__/InputFieldCustomer.mock';
import CustomerSignUpComponent from '../index';

const mockNavigate = jest.fn();

jest.mock('@mui/icons-material/Close', () => ({
  __esModule: true,
  default: CloseIconMock,
}));

jest.mock('../../../UI/customer/InputFieldCustomer', () => ({
  __esModule: true,
  default: MockInputFieldCustomer,
}));
jest.mock('../../../UI/common/PasswordField', () => ({
  __esModule: true,
  default: MockPasswordField,
}));
jest.mock('../../../UI/customer/ButtonCustomer', () => ({
  __esModule: true,
  default: MockButtonCustomer,
}));

jest.mock('@services/http/public/auth', () => ({
  signUp: jest.fn(),
}));

jest.mock('../../../../store/store', () => ({
  useDispatch: () => jest.fn(),
}));

jest.mock('../../../../store/reducers/auth', () => ({
  setCredentials: (payload: any) => ({ type: 'auth/setCredentials', payload }),
}));

jest.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock validation schema
jest.mock('../validation', () => {
  const real = jest.requireActual('../validation');
  const mockSchema = z.object({
    firstName: z.string().min(1, 'Required'),
    lastName: z.string().min(1, 'Required'),
    email: z.string().email('Invalid email'),
    password: z.string().min(6, 'Too short'),
  });
  return {
    ...real,
    signUpSchema: mockSchema,
  };
});

describe('CustomerSignUpComponent', () => {
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders all fields and buttons', () => {
    render(<CustomerSignUpComponent onClose={mockOnClose} />);
    expect(screen.getByTestId('close-icon')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('First Name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Last Name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
    expect(screen.getByTestId('button-sign-up')).toBeInTheDocument();
  });

  test('sign up button disabled initially', () => {
    render(<CustomerSignUpComponent onClose={mockOnClose} />);
    expect(screen.getByTestId('button-sign-up')).toBeDisabled();
  });

  test('enables button when all fields valid', async () => {
    render(<CustomerSignUpComponent onClose={mockOnClose} />);
    await userEvent.type(screen.getByPlaceholderText('First Name'), 'John');
    await userEvent.type(screen.getByPlaceholderText('Last Name'), 'Doe');
    await userEvent.type(
      screen.getByPlaceholderText('Email'),
      'john@example.com'
    );
    await userEvent.type(screen.getByPlaceholderText('Password'), 'Secret123');

    await waitFor(() => {
      expect(screen.getByTestId('button-sign-up')).not.toBeDisabled();
    });
  });

  test('submits correct data and navigates on success', async () => {
    (authService.signUp as jest.Mock).mockResolvedValueOnce({
      access: 't1',
      refresh: 't2',
    });

    render(<CustomerSignUpComponent onClose={mockOnClose} />);
    await userEvent.type(screen.getByPlaceholderText('First Name'), 'Alice');
    await userEvent.type(screen.getByPlaceholderText('Last Name'), 'Smith');
    await userEvent.type(screen.getByPlaceholderText('Email'), 'alice@x.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), 'Password1');

    await waitFor(() => {
      expect(screen.getByTestId('button-sign-up')).not.toBeDisabled();
    });

    await userEvent.click(screen.getByTestId('button-sign-up'));

    await waitFor(() => {
      expect(authService.signUp).toHaveBeenCalledWith({
        first_name: 'Alice',
        last_name: 'Smith',
        email: 'alice@x.com',
        password: 'Password1',
      });
    });

    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  test('displays server root error on failure', async () => {
    (authService.signUp as jest.Mock).mockRejectedValueOnce({
      response: { data: { detail: 'Server error' } },
      isAxiosError: true,
    });

    render(<CustomerSignUpComponent onClose={mockOnClose} />);
    await userEvent.type(screen.getByPlaceholderText('First Name'), 'A');
    await userEvent.type(screen.getByPlaceholderText('Last Name'), 'B');
    await userEvent.type(screen.getByPlaceholderText('Email'), 'a@b.com');
    await userEvent.type(screen.getByPlaceholderText('Password'), '123456');

    await waitFor(() => {
      expect(screen.getByTestId('button-sign-up')).not.toBeDisabled();
    });

    await userEvent.click(screen.getByTestId('button-sign-up'));

    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument();
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  test('close button triggers onClose', async () => {
    render(<CustomerSignUpComponent onClose={mockOnClose} />);
    const btn = screen.getByTestId('close-icon').closest('button')!;
    await userEvent.click(btn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  test('updates RuleTag based on password input', async () => {
    render(<CustomerSignUpComponent onClose={mockOnClose} />);

    const passwordField = screen.getByPlaceholderText('Password');

    expect(screen.queryByTestId('password-rule-check')).not.toBeInTheDocument();

    // Enter not valid password and check if 3 rules is active
    await userEvent.type(passwordField, 'Pass1');

    await waitFor(() => {
      const checks = screen.getAllByTestId('password-rule-check');
      expect(checks.length).toBe(3);
    });

    // Check with valid password
    await userEvent.clear(passwordField);
    await userEvent.type(passwordField, 'Corr3ctP@ssword');

    await waitFor(() => {
      const checks = screen.getAllByTestId('password-rule-check');
      expect(checks.length).toBe(5);
    });
  });
});
