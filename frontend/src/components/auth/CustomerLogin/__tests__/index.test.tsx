import '@testing-library/jest-dom';
import { configure, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { z } from 'zod';

import CloseIconMock from '@/__mocks__/CloseIcon.mock';
import MockPasswordField from '@components/UI/common/PasswordField/__mocks__/pwdField.mock';
import MockButtonCustomer from '@components/UI/customer/ButtonCustomer/__mocks__/ButtonCustomer.mock';
import { MockInputFieldCustomer } from '@components/UI/customer/InputFieldCustomer/__mocks__/InputFieldCustomer.mock';
import * as authService from '@services/http/public/auth';
import * as cartService from '@services/http/public/cart';
import CustomerLoginComponent from '../index';

configure({ asyncUtilTimeout: 5000 });
// Mock various dependencies
jest.mock('quill', () => {
  return function Quill() {
    return {
      getContents: () => ({}),
      on: () => {},
      clipboard: {
        addMatcher: () => {},
      },
    };
  };
});

// Mock UI components
jest.mock('@components/UI/customer/InputFieldCustomer', () => ({
  __esModule: true,
  default: MockInputFieldCustomer,
}));

jest.mock('@components/UI/common/PasswordField', () => ({
  __esModule: true,
  default: MockPasswordField,
}));

jest.mock('@components/UI/customer/ButtonCustomer', () => ({
  __esModule: true,
  default: MockButtonCustomer,
}));

jest.mock('@mui/icons-material/Close', () => ({
  __esModule: true,
  default: CloseIconMock,
}));

// Mock validation schema to test form behavior
jest.mock('../validation', () => {
  const mockSchema = z.object({
    email: z.string().email('Please enter a valid email address'),
    password: z
      .string()
      .min(6, 'Please enter a valid password')
      .refine(() => true, { message: 'Please enter a valid password' }),
    root: z.string().optional(),
  });

  return {
    validateField: jest.fn(),
    loginSchema: mockSchema,
    hasRequiredComplexity: jest.fn().mockReturnValue(true),
  };
});

// Mock React Router
const mockNavigate = jest.fn();
jest.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock Redux store
const mockDispatch = jest.fn();
jest.mock('@store/store', () => ({
  useDispatch: () => mockDispatch,
}));

// Mock login service
jest.mock('@services/http/public/auth', () => ({
  login: jest.fn(),
}));

jest.mock('@services/http/public/cart', () => ({
  mergeCart: jest.fn(),
}));

// Mock the Redux action creator
jest.mock('@store/reducers/auth', () => {
  // Create a mock action creator that returns an action object with the correct shape
  const mockSetCredentials = (payload: any) => ({
    type: 'auth/setCredentials',
    payload,
  });

  return {
    setCredentials: mockSetCredentials,
  };
});

jest.mock('axios', () => ({
  isAxiosError: (error: any) => error.isAxiosError,
}));

// Fix: Properly mock parseApiErrors utility to return complete error messages
jest.mock('@utils/parseAPIErrors', () => ({
  parseApiErrors: jest.fn().mockImplementation(error => {
    if (error?.response?.data?.detail) {
      return { root: error.response.data.detail };
    }
    if (error?.response?.data?.email) {
      // Fix: Return the full error message
      return { email: error.response.data.email };
    }
    if (error?.response?.data?.password) {
      return { password: error.response.data.password };
    }
    return { root: 'An unknown error occurred' };
  }),
}));

describe('CustomerLoginComponent', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 1. RENDERING TESTS

  test('renders login form with all elements', () => {
    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );

    // Check title
    expect(screen.getByTestId('login-title')).toHaveTextContent('Log in');

    // Check form fields
    expect(screen.getByTestId('email-input')).toBeInTheDocument();
    expect(screen.getByTestId('password-input')).toBeInTheDocument();

    // Check buttons
    expect(screen.getByTestId('button-log-in')).toBeInTheDocument();
    expect(screen.getByTestId('button-sign-up')).toBeInTheDocument();

    // Check close button
    expect(screen.getByTestId('close-icon')).toBeInTheDocument();
  });

  test('login button should be disabled initially', () => {
    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );
    expect(screen.getByTestId('button-log-in')).toBeDisabled();
  });

  // 2. FORM VALIDATION TESTS

  test('enables login button when form fields have values', async () => {
    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );

    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    // Fix: Use userEvent without act() wrapper
    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'Password123!');

    // Wait for button state to update
    await waitFor(() => {
      expect(screen.getByTestId('button-log-in')).not.toBeDisabled();
    });
  });

  // 3. FORM SUBMISSION TESTS

  test('submits form with correct values when login button is clicked', async () => {
    // Mock successful login
    const mockLoginResponse = {
      access: 'fake-access-token',
      refresh: 'fake-refresh-token',
    };

    (authService.login as jest.Mock).mockResolvedValueOnce(mockLoginResponse);

    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );

    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    // Fix: Use userEvent without act() wrapper
    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'Password123!');

    // Wait for the button to be enabled
    await waitFor(() => {
      expect(screen.getByTestId('button-log-in')).not.toBeDisabled();
    });

    // Submit the form
    await userEvent.click(screen.getByTestId('button-log-in'));

    // Verify login function was called with correct credentials
    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'Password123!',
      });
      expect(cartService.mergeCart).toHaveBeenCalledWith(
        mockLoginResponse.access
      );
    });

    // Verify that dispatch was called with an action object having the right shape
    await waitFor(() => {
      expect(mockDispatch).toHaveBeenCalledWith({
        type: 'auth/setCredentials',
        payload: mockLoginResponse,
      });
    });

    // Verify navigation to home page
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  test('displays server error when login fails', async () => {
    // Mock failed login
    const errorResponse = {
      response: {
        data: { detail: 'Invalid credentials' },
      },
      isAxiosError: true,
    };

    (authService.login as jest.Mock).mockRejectedValueOnce(errorResponse);

    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );

    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    // Fix: Use userEvent without act() wrapper
    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'Password123!');

    // Wait for button to be enabled
    await waitFor(() => {
      expect(screen.getByTestId('button-log-in')).not.toBeDisabled();
    });

    // Submit the form
    await userEvent.click(screen.getByTestId('button-log-in'));

    // Wait for error message to appear
    await waitFor(() => {
      // Using getByText since the error might be in a different element than expected
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });

    // Verify that navigation was not called
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('displays field-specific error when server returns field error', async () => {
    // Fix: Change the error response structure to match what the component expects
    const errorResponse = {
      response: {
        data: {
          email: 'This email is already registered', // Not an array now
        },
      },
      isAxiosError: true,
    };

    (authService.login as jest.Mock).mockRejectedValueOnce(errorResponse);

    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );

    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    // Fix: Use userEvent without act() wrapper
    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'Password123!');

    // Wait for button to be enabled
    await waitFor(() => {
      expect(screen.getByTestId('button-log-in')).not.toBeDisabled();
    });

    // Submit the form
    await userEvent.click(screen.getByTestId('button-log-in'));

    // Wait for field error to appear
    await waitFor(() => {
      const errorElement = screen.getByTestId('email-error');
      expect(errorElement).toHaveTextContent(
        'This email is already registered'
      );
    });
  });

  // 4. UI INTERACTION TESTS

  test('close button triggers onClose handler', async () => {
    const mockOnClose = jest.fn();
    render(
      <CustomerLoginComponent
        switchToSignUp={jest.fn()}
        onClose={mockOnClose}
      />
    );
    const closeBtn = screen.getByTestId('close-icon').closest('button');
    await userEvent.click(closeBtn!);
    expect(mockOnClose).toHaveBeenCalled();
  });

  test('sign up button is not disabled', () => {
    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );
    const signUpButton = screen.getByTestId('button-sign-up');
    expect(signUpButton).not.toBeDisabled();
  });

  test('login button shows loading state during submission', async () => {
    // Mock slow login response
    (authService.login as jest.Mock).mockImplementation(() => {
      return new Promise(resolve => {
        setTimeout(() => {
          resolve({
            access: 'fake-access-token',
            refresh: 'fake-refresh-token',
          });
        }, 100);
      });
    });

    render(
      <CustomerLoginComponent switchToSignUp={jest.fn()} onClose={jest.fn()} />
    );

    const emailInput = screen.getByTestId('email-input');
    const passwordInput = screen.getByTestId('password-input');

    // Fix: Use userEvent without act() wrapper
    await userEvent.type(emailInput, 'test@example.com');
    await userEvent.type(passwordInput, 'Password123!');

    // Wait for button to be enabled
    await waitFor(() => {
      expect(screen.getByTestId('button-log-in')).not.toBeDisabled();
    });

    // Submit the form
    await userEvent.click(screen.getByTestId('button-log-in'));

    // Check loading state
    await waitFor(() => {
      expect(screen.getByTestId('button-log-in')).toHaveAttribute(
        'data-loading',
        'true'
      );
    });

    // Wait for submission to complete
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/');
      },
      { timeout: 2000 }
    ); // Increase timeout to account for slow response
  });
});
