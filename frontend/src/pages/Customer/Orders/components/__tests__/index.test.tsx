import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
  IOrderItemPublic,
  IOrderPublic,
} from '../../../../../types/orders/interfaces';
import Order from '@pages/Customer/Orders/components/Order';
import * as orderService from '@services/http/public/orders';
import '@testing-library/jest-dom';
import { PaginatedResults } from '../../../../../types/pagination/interfaces';

jest.mock('@components/UI/icons/StripeIcon', () => {
  return {
    __esModule: true,
    default: () => <div data-testid={'stripe-icon'}>Stripe</div>,
  };
});

const mockOrder: IOrderPublic = {
  id: '1',
  createdAt: new Date(),
  status: 'new',
  totalCost: '100',
  itemsAmount: 4,
  contactInfo: {
    id: 1,
    firstName: 'John',
    lastName: 'Doe',
    phone: '1234567890',
    email: 'john@example.com',
    deliveryAddress: '123 Street',
  },
};

const mockOrderItems: PaginatedResults<IOrderItemPublic> = {
  results: [
    {
      id: '1',
      price: '10',
      quantity: 2,
      totalPrice: '20',
      product: {
        id: '1',
        name: 'Test Product',
        image: undefined,
      },
    },
  ],
  previous: undefined,
  next: undefined,
  count: 1,
};

jest.spyOn(orderService, 'getOrderItems').mockResolvedValue(mockOrderItems);

describe('Order component', () => {
  it('renders order summary', () => {
    render(<Order order={mockOrder} />);
    expect(screen.getByText(/Order #1/)).toBeInTheDocument();
    expect(screen.getByText(/Contact Details/)).not.toBeVisible();
  });

  it('expands and loads order items', async () => {
    render(<Order order={mockOrder} />);

    const header = screen.getByText(/Order #1/).closest('div');
    fireEvent.click(header!);

    await waitFor(() => {
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('$10')).toBeInTheDocument();
    });
  });

  it('shows control buttons depending on order status', async () => {
    render(<Order order={{ ...mockOrder, status: 'pending' }} />);

    const header = screen.getByText(/Order #1/).closest('div');
    fireEvent.click(header!);

    await waitFor(() => {
      expect(screen.getByTestId('stripe-icon')).toBeInTheDocument();
    });
  });
});
