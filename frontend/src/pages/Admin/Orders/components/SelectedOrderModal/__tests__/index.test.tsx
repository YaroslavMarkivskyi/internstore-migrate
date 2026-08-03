import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SelectedOrderModal from '@pages/Admin/Orders/components/SelectedOrderModal';
import * as ordersService from '@services/http/admin/orders';

const mockOrder = {
  id: 1,
  status: 'Pending',
  contactInfo: {
    firstName: 'John',
    lastName: 'Doe',
    email: 'john@example.com',
    phone: '1234567890',
    deliveryAddress: '123 Main St',
  },
  totalCost: 123,
};

const mockOrderItems = {
  results: [
    {
      id: 101,
      product: {
        id: 101,
        name: 'Product A',
        image: null,
        category: { name: 'Category 1' },
      },
      price: 10,
      quantity: 2,
      availableQuantity: 5,
      totalPrice: 20,
    },
  ],
  next: null,
};

jest.mock('@services/http/admin/orders', () => ({
  getOrder: jest.fn(),
  getOrderItems: jest.fn(),
}));

describe('SelectedOrderModal', () => {
  const getOrderMock = ordersService.getOrder as jest.Mock;
  const getOrderItemsMock = ordersService.getOrderItems as jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading spinner when order is null', async () => {
    getOrderMock.mockResolvedValueOnce(mockOrder);
    getOrderItemsMock.mockResolvedValueOnce(mockOrderItems);
    render(
      <SelectedOrderModal open={true} selectedOrderId={'1'} onClose={jest.fn()} />
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('renders order data and items after loading', async () => {
    getOrderMock.mockResolvedValueOnce(mockOrder);
    getOrderItemsMock.mockResolvedValueOnce(mockOrderItems);

    render(
      <SelectedOrderModal open={true} selectedOrderId={'1'} onClose={jest.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('Client Information')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Product A')).toBeInTheDocument();
    });
  });

  it('renders buttons based on order status', async () => {
    getOrderMock.mockResolvedValueOnce({ ...mockOrder, status: 'new' });
    getOrderItemsMock.mockResolvedValueOnce(mockOrderItems);

    render(
      <SelectedOrderModal open={true} selectedOrderId={'1'} onClose={jest.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('Send an invoice')).toBeInTheDocument();
    });
  });

  it('handles sort button click', async () => {
    getOrderMock.mockResolvedValueOnce(mockOrder);
    getOrderItemsMock.mockResolvedValue(mockOrderItems);

    render(
      <SelectedOrderModal open={true} selectedOrderId={'1'} onClose={jest.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('Price')).toBeInTheDocument();
    });

    const sortButton = screen.getByRole('button', { name: /sort by price/i });
    fireEvent.click(sortButton);

    await waitFor(() => {
      expect(getOrderItemsMock).toHaveBeenCalled();
    });
  });
});
