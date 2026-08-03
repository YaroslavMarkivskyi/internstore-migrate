import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CustomMenuItemMock from '@components/UI/admin/CustomMenuItem/__mocks__/index.mock';
import UserModal from '../index';
import { useNavigate, useLocation } from 'react-router';
import { logout } from '@services/http/public/auth';

// Mock dependencies
jest.mock('react-router', () => ({
  useNavigate: jest.fn(),
  useLocation: jest.fn(),
}));

jest.mock('@services/http/public/auth', () => ({
  logout: jest.fn().mockResolvedValue({}),
}));

// Mock activity detection utility
jest.mock('@utils/activityDetection', () => ({
  hasUserActivity: jest.fn(),
}));

// Mock showToast utility
jest.mock('@utils/showToast', () => ({
  __esModule: true,
  default: jest.fn(),
}));

// Mock LogoutConfirmationModal - use jest.fn() directly in factory
jest.mock('../components/LogoutConfirmationModal', () => ({
  __esModule: true,
  default: jest.fn(),
}));

// Import the mocked functions for type safety
import { hasUserActivity } from '@utils/activityDetection';
import showToast from '@utils/showToast';
import LogoutConfirmationModal from '../components/LogoutConfirmationModal';

// Get reference to the mocked component
const mockLogoutConfirmationModal =
  LogoutConfirmationModal as jest.MockedFunction<
    typeof LogoutConfirmationModal
  >;

// Mock Redux hooks
const mockUseSelector = jest.fn();
const mockDispatch = jest.fn();
const mockUseDispatch = jest.fn(() => mockDispatch);

jest.mock('@store/store', () => ({
  useDispatch: () => mockUseDispatch(),
  useSelector: (selector: any) => mockUseSelector(selector),
}));

// Mock Material UI icons
jest.mock('@mui/icons-material/AccountCircleOutlined', () => ({
  __esModule: true,
  default: () => <div data-testid="account-icon">AccountIcon</div>,
}));

jest.mock('@mui/icons-material/LogoutOutlined', () => ({
  __esModule: true,
  default: () => <div data-testid="logout-icon">LogoutIcon</div>,
}));

// Mock CustomMenuItem component
jest.mock('../../UI/admin/CustomMenuItem', () => ({
  __esModule: true,
  default: CustomMenuItemMock,
}));

// Helper function to check if any call matches the expected props
const hasCallWithProps = (
  mockFn: jest.MockedFunction<any>,
  expectedProps: Record<string, any>
) => {
  return mockFn.mock.calls.some((call: any[]) => {
    const [props] = call;
    if (!props || typeof props !== 'object') return false;
    return Object.keys(expectedProps).every(
      key => props[key] === expectedProps[key]
    );
  });
};

// Helper function to get the latest call props
const getLatestCallProps = (mockFn: jest.MockedFunction<any>) => {
  const calls = mockFn.mock.calls;
  return calls.length > 0 ? calls[calls.length - 1][0] : null;
};

describe('UserModal Component', () => {
  // Mock navigation function
  const mockNavigate = jest.fn();
  const mockLocation = { pathname: '/dashboard' };

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();

    // Setup useNavigate mock
    (useNavigate as jest.Mock).mockReturnValue(mockNavigate);

    // Setup useLocation mock
    (useLocation as jest.Mock).mockReturnValue(mockLocation);

    // Setup LogoutConfirmationModal mock to render nothing by default
    mockLogoutConfirmationModal.mockImplementation(() => null);

    // Setup activity detection to return false by default
    (hasUserActivity as jest.Mock).mockReturnValue(false);
  });

  test('renders both menu items correctly', () => {
    // Setup mock state
    mockUseSelector.mockImplementation(_selector => {
      return null;
    });

    render(<UserModal />);

    // Check if both menu items are rendered
    expect(screen.getByTestId('menu-item-my-profile')).toBeInTheDocument();
    expect(screen.getByTestId('menu-item-log-out')).toBeInTheDocument();

    // Check if icons are rendered
    expect(screen.getByTestId('account-icon')).toBeInTheDocument();
    expect(screen.getByTestId('logout-icon')).toBeInTheDocument();
  });

  test('navigates to profile page when "My profile" is clicked', () => {
    // Setup mock state
    mockUseSelector.mockImplementation(_selector => {
      return null;
    });

    render(<UserModal />);

    // Click on the profile menu item
    fireEvent.click(screen.getByTestId('menu-item-my-profile'));

    // Check if navigation was called with correct path
    expect(mockNavigate).toHaveBeenCalledWith('/profile/orders');
  });

  test('performs direct logout when no activity is detected', async () => {
    // Setup mock state for regular user
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: 'mock-refresh-token',
          currentUser: { id: 1, is_admin: false },
        },
      };
      return selector(state);
    });

    // Mock no activity detected
    (hasUserActivity as jest.Mock).mockReturnValue(false);

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Check that activity detection was called with current pathname
    expect(hasUserActivity).toHaveBeenCalledWith('/dashboard');

    // Check that confirmation modal never opens (no call should have isOpen: true)
    expect(
      hasCallWithProps(mockLogoutConfirmationModal, { isOpen: true })
    ).toBe(false);

    // Wait for async operations to complete
    await waitFor(() => {
      // Check if logout API was called
      expect(logout).toHaveBeenCalledWith({ refresh: 'mock-refresh-token' });
      // Check if navigation occurred
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  test('shows confirmation modal when activity is detected', async () => {
    // Setup mock state for regular user
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: 'mock-refresh-token',
          currentUser: { id: 1, is_admin: false },
        },
      };
      return selector(state);
    });

    // Mock activity detected
    (hasUserActivity as jest.Mock).mockReturnValue(true);

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Check that activity detection was called
    expect(hasUserActivity).toHaveBeenCalledWith('/dashboard');

    // Check that confirmation modal opens (at least one call should have isOpen: true)
    await waitFor(() => {
      expect(
        hasCallWithProps(mockLogoutConfirmationModal, { isOpen: true })
      ).toBe(true);
    });

    // Check that the latest call has the expected loading state
    const latestProps = getLatestCallProps(mockLogoutConfirmationModal);
    expect(latestProps).toMatchObject({
      isOpen: true,
      isLoading: false,
    });

    // Check that logout API was NOT called immediately
    expect(logout).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('performs logout when user confirms despite activity', async () => {
    // Setup mock state for admin user
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: 'mock-refresh-token',
          currentUser: { id: 1, is_admin: true },
        },
      };
      return selector(state);
    });

    // Mock activity detected
    (hasUserActivity as jest.Mock).mockReturnValue(true);

    // Mock LogoutConfirmationModal to capture and call onConfirm
    let capturedOnConfirm: (() => void) | undefined;
    mockLogoutConfirmationModal.mockImplementation(({ onConfirm }) => {
      capturedOnConfirm = onConfirm;
      return null;
    });

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Simulate user confirming logout
    expect(capturedOnConfirm).toBeDefined();
    if (capturedOnConfirm) {
      await capturedOnConfirm();
    }

    // Wait for async operations to complete
    await waitFor(() => {
      // Check if logout API was called
      expect(logout).toHaveBeenCalledWith({ refresh: 'mock-refresh-token' });
      // Check if admin navigation occurred
      expect(mockNavigate).toHaveBeenCalledWith('/admin/login/');
      // Check if success toast was shown
      expect(showToast).toHaveBeenCalledWith({
        message: 'Successfully signed out.',
        type: 'success',
      });
    });
  });

  test('cancels logout when user chooses to stay', async () => {
    // Setup mock state
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: 'mock-refresh-token',
          currentUser: { id: 1, is_admin: false },
        },
      };
      return selector(state);
    });

    // Mock activity detected
    (hasUserActivity as jest.Mock).mockReturnValue(true);

    // Mock LogoutConfirmationModal to capture and call onCancel
    let capturedOnCancel: (() => void) | undefined;
    mockLogoutConfirmationModal.mockImplementation(({ onCancel }) => {
      capturedOnCancel = onCancel;
      return null;
    });

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Wait for modal to open
    await waitFor(() => {
      expect(
        hasCallWithProps(mockLogoutConfirmationModal, { isOpen: true })
      ).toBe(true);
    });

    // Simulate user canceling logout
    expect(capturedOnCancel).toBeDefined();
    if (capturedOnCancel) {
      capturedOnCancel();
    }

    // Check that modal eventually closes
    await waitFor(() => {
      const latestProps = getLatestCallProps(mockLogoutConfirmationModal);
      expect(latestProps).toMatchObject({ isOpen: false });
    });

    // Check that no logout occurred
    expect(logout).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('handles logout error gracefully', async () => {
    // Setup mock state
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: 'mock-refresh-token',
          currentUser: { id: 1, is_admin: false },
        },
      };
      return selector(state);
    });

    // Mock logout API to throw error
    (logout as jest.Mock).mockRejectedValue(new Error('Network error'));

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Wait for async operations to complete
    await waitFor(() => {
      // Check if error toast was shown
      expect(showToast).toHaveBeenCalledWith({
        message: 'Error during logout, please try again.',
        type: 'error',
      });
    });
  });

  test('does not perform logout when refreshToken or currentUser is missing', async () => {
    // Setup mock state with no tokens or user
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: null,
          currentUser: null,
        },
      };
      return selector(state);
    });

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Check that activity detection was still called
    expect(hasUserActivity).toHaveBeenCalledWith('/dashboard');

    // Check that no logout API call was made
    expect(logout).not.toHaveBeenCalled();

    // Check that no navigation occurred
    expect(mockNavigate).not.toHaveBeenCalled();

    // Check that no action was dispatched
    expect(mockDispatch).not.toHaveBeenCalled();
  });

  test('activity detection works with different pathnames', async () => {
    // Setup mock state
    mockUseSelector.mockImplementation(selector => {
      const state = {
        auth: {
          refreshToken: 'mock-refresh-token',
          currentUser: { id: 1, is_admin: false },
        },
      };
      return selector(state);
    });

    // Mock location with activity route
    (useLocation as jest.Mock).mockReturnValue({ pathname: '/products/add' });
    (hasUserActivity as jest.Mock).mockReturnValue(true);

    render(<UserModal />);

    // Click on logout menu item
    fireEvent.click(screen.getByTestId('menu-item-log-out'));

    // Check that activity detection was called with correct pathname
    expect(hasUserActivity).toHaveBeenCalledWith('/products/add');

    // Check that confirmation modal opens (at least one call should have isOpen: true)
    await waitFor(() => {
      expect(
        hasCallWithProps(mockLogoutConfirmationModal, { isOpen: true })
      ).toBe(true);
    });
  });
});
