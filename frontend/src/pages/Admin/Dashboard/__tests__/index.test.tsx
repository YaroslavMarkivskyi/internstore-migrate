import { render, screen } from '@testing-library/react';
import AdminDashboard from '../index';

// Mock the DashboardContent component
jest.mock('../components/DashboardContent', () => {
  return {
    __esModule: true,
    default: () => (
      <div data-testid="dashboard-content">Mocked Dashboard Content</div>
    ),
  };
});

describe('AdminDashboard Page', () => {
  test('renders DashboardContent component', () => {
    render(<AdminDashboard />);

    // Assert that DashboardContent is rendered
    const dashboardContent = screen.getByTestId('dashboard-content');
    expect(dashboardContent).toBeInTheDocument();
    expect(dashboardContent).toHaveTextContent('Mocked Dashboard Content');
  });
});
