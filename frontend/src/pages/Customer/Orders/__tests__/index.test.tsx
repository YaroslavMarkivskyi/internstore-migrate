import { render, screen } from '@testing-library/react';
import Orders from '@pages/Customer/Orders';
import useOrders from '@pages/Customer/Orders/hooks/useOrders';
import '@testing-library/jest-dom';

jest.mock('@pages/Customer/Orders/hooks/useOrders');
jest.mock('@components/UI/icons/StripeIcon', () => (
  <div data-testid={'stripe-icon'}>Stripe</div>
));

const mockUseOrders = useOrders as jest.Mock;

describe('Orders component', () => {
  beforeEach(() => {
    mockUseOrders.mockReturnValue({
      orders: [],
      setPage: jest.fn(),
      count: 18,
      isLoading: false,
      page: 1,
      limit: 8,
    });
  });

  it('renders title and pagination', async () => {
    render(<Orders />);
    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByTestId('ArrowBackIosIcon')).toBeInTheDocument(); // Pagination
    expect(screen.getByTestId('ArrowForwardIosIcon')).toBeInTheDocument(); // Pagination
  });

  it('shows loading spinner when loading', () => {
    mockUseOrders.mockReturnValue({
      orders: [],
      setPage: jest.fn(),
      count: 0,
      isLoading: true,
      page: 1,
      limit: 8,
    });

    render(<Orders />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows nothing found message when no orders', () => {
    render(<Orders />);
    expect(screen.getByText('There is nothing yet..')).toBeInTheDocument();
  });
});
