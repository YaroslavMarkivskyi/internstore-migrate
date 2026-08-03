import { render, screen } from '@testing-library/react';
import DashboardContent from '../index';

// Mock the child components
jest.mock('../DashboardTiles', () => {
  return {
    __esModule: true,
    default: () => (
      <div data-testid="dashboard-tiles">Mocked Dashboard Tiles</div>
    ),
  };
});

jest.mock('../UnprocessedOrders', () => {
  return {
    __esModule: true,
    default: () => (
      <div data-testid="unprocessed-orders">Mocked Unprocessed Orders</div>
    ),
  };
});

describe('DashboardContent Component', () => {
  test('renders all dashboard components correctly', () => {
    render(<DashboardContent />);

    // Check if the dashboard title is rendered
    const title = screen.getByText('Dashboard');
    expect(title).toBeInTheDocument();

    // Check if DashboardTiles component is rendered
    const tiles = screen.getByTestId('dashboard-tiles');
    expect(tiles).toBeInTheDocument();
    expect(tiles).toHaveTextContent('Mocked Dashboard Tiles');

    // Check if UnprocessedOrders component is rendered
    const orders = screen.getByTestId('unprocessed-orders');
    expect(orders).toBeInTheDocument();
    expect(orders).toHaveTextContent('Mocked Unprocessed Orders');
  });
});
