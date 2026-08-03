import { fireEvent, screen, waitFor } from '@testing-library/react';
import Cart from '../';
import * as cartService from '@services/http/public/cart';
import { CartProvider } from '../../../../../hooks/useCart';
import { useSelector } from '@store/store';
import { selectCurrentUser } from '@store/reducers/auth';
import { renderWithRouter } from '@utils/testRenderWithRouter';

jest.mock('@store/store', () => ({ useSelector: jest.fn() }));
jest.mock('@services/http/public/cart');
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

const mockItems = [
  {
    id: 1,
    product: { id: 1, name: 'Test Product', price: '5.00', image: 'test.jpg' },
    quantity: 2,
  },
];
const mockCart = { totalCost: '10.00' };
const mockUser = { id: 123, name: 'Test User' };

describe('Cart', () => {
  beforeEach(() => {
    (useSelector as jest.Mock).mockImplementation(selector => {
      if (selector === selectCurrentUser) return mockUser;
      return undefined;
    });
    (cartService.getCartItems as jest.Mock).mockResolvedValue({
      results: mockItems,
      next: null,
      count: 1,
    });
    (cartService.getCart as jest.Mock).mockResolvedValue(mockCart);
    (cartService.removeItemFromCart as jest.Mock).mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('displays cart items and total', async () => {
    renderWithRouter(
      <CartProvider>
        <Cart open={true} onClose={jest.fn()} />
      </CartProvider>
    );

    expect(await screen.findByText('Test Product')).toBeInTheDocument();
    expect(screen.getByText('$5.00')).toBeInTheDocument();
    expect(screen.getByText('Total:')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
  });

  it('deletes an item when clicking Delete', async () => {
    renderWithRouter(
      <CartProvider>
        <Cart open={true} onClose={jest.fn()} />
      </CartProvider>
    );

    const deleteButton = await screen.findByRole('button', { name: /delete/i });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(cartService.removeItemFromCart).toHaveBeenCalledWith(1);
    });
  });
});
