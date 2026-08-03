import { render, screen } from '@testing-library/react';
import AdminOrders from '../index';

// Mock child components
jest.mock('../components/OrdersFilter', () => ({
  __esModule: true,
  default: () => <div data-testid="orders-filter">Mocked Orders Filter</div>,
}));

jest.mock('../components/OrdersTable', () => ({
  __esModule: true,
  default: ({ orders, isLoading }: { orders: any[]; isLoading: boolean }) => (
    <div data-testid="orders-table">
      {isLoading ? 'Loading...' : `Orders count: ${orders.length}`}
    </div>
  ),
}));

jest.mock('../components/OrdersPagination', () => ({
  __esModule: true,
  default: ({ count, currentPage }: { count: number; currentPage: number }) =>
    count > 1 && (
      <div data-testid="orders-pagination">
        Page {currentPage} of {count}
      </div>
    ),
}));

jest.mock('../hooks/useFilterOrders', () => ({
  __esModule: true,
  default: jest.fn(),
}));

import useFilterOrders from '../hooks/useFilterOrders';

describe('AdminOrders Page', () => {
  const mockUseFilterOrders = useFilterOrders as jest.Mock;

  beforeEach(() => {
    mockUseFilterOrders.mockReturnValue({
      orders: [{ id: 1 }, { id: 2 }],
      isLoading: false,
      count: 2,
      setPage: jest.fn(),
      page: 1,
      deleteFilter: jest.fn(),
      setFilters: jest.fn(),
      limit: 2,
      ordering: 'new',
      status: ['new'],
      archived: false,
      date: [],
    });
  });

  test('renders main components', () => {
    render(<AdminOrders />);

    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByTestId('orders-filter')).toBeInTheDocument();
    expect(screen.getByTestId('orders-table')).toBeInTheDocument();
  });

  test('renders orders table with data', () => {
    render(<AdminOrders />);
    const ordersTable = screen.getByTestId('orders-table');
    expect(ordersTable).toBeInTheDocument();
    expect(ordersTable).toHaveTextContent('Orders count: 2');
  });

  test('does not render pagination when only one page', () => {
    mockUseFilterOrders.mockReturnValueOnce({
      orders: [{ id: 1 }, { id: 2 }],
      isLoading: false,
      count: 2,
      limit: 8,
      page: 1,
      setPage: jest.fn(),
      deleteFilter: jest.fn(),
      setFilters: jest.fn(),
      ordering: 'new',
      status: [],
      archived: false,
      date: [],
    });

    render(<AdminOrders />);
    const pagination = screen.queryByTestId('orders-pagination');
    expect(pagination).not.toBeInTheDocument();
  });

  test('renders pagination if more than one page', () => {
    mockUseFilterOrders.mockReturnValueOnce({
      orders: new Array(8).fill({ id: 1 }),
      isLoading: false,
      count: 16,
      limit: 8,
      page: 1,
      setPage: jest.fn(),
      deleteFilter: jest.fn(),
      setFilters: jest.fn(),
      ordering: 'new',
      status: [],
      archived: false,
      date: [],
    });

    render(<AdminOrders />);
    expect(screen.getByTestId('orders-pagination')).toHaveTextContent(
      'Page 1 of 2'
    );
  });
});
