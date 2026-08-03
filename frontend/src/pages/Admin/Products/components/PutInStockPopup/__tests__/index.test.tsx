import '@testing-library/jest-dom';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import PutInStockPopup from '..';
import { getStocks, bulkAddStocks } from '@services/http/admin/stocks';
import { getProduct } from '@services/http/admin/products';
import showToast from '@utils/showToast';

// Mocks
jest.mock('@services/http/admin/stocks', () => ({
  getStocks: jest.fn(),
  bulkAddStocks: jest.fn(),
}));

jest.mock('@services/http/admin/products', () => ({
  getProduct: jest.fn(),
}));

jest.mock('@utils/showToast', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('../components/ConfirmModal', () => ({
  __esModule: true,
  default: ({ open, onClose, onConfirm, stocks }: any) => (
    <div
      data-testid="confirm-modal"
      style={{ display: open ? 'block' : 'none' }}
    >
      <button data-testid="close-modal" onClick={onClose}>
        Close
      </button>
      <button data-testid="confirm-modal-button" onClick={onConfirm}>
        Confirm
      </button>
      <div data-testid="stocks-count">{stocks.length}</div>
    </div>
  ),
}));

describe('PutInStockPopup', () => {
  const mockClose = jest.fn();
  const mockConfirm = jest.fn();
  const anchorEl = document.createElement('div');

  const mockProduct = {
    id: '123',
    name: 'Test Product',
    price: '10.00',
    minTemperature: 5,
    maxTemperature: 25,
    category: { id: '1', name: 'Test Category' },
    description: 'Test Description',
    isPublished: true,
    image: 'test-image.jpg',
    totalQuantity: 100,
  };

  const mockStocks = [
    { id: 1, name: 'Stock 1' },
    { id: 2, name: 'Stock 2' },
    { id: 3, name: 'Stock 3' },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    (getStocks as jest.Mock).mockResolvedValue(mockStocks);
    (getProduct as jest.Mock).mockResolvedValue(mockProduct);
    (bulkAddStocks as jest.Mock).mockResolvedValue({});
  });

  test('renders the popup when open is true', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    expect(screen.getByText('Put in stock')).toBeInTheDocument();
    expect(getStocks).toHaveBeenCalled();
  });

  test('does not render the popup when open is false', () => {
    render(
      <PutInStockPopup
        open={false}
        anchorEl={anchorEl}
        onClose={mockClose}
        onConfirm={mockConfirm}
        product={mockProduct}
      />
    );

    expect(screen.queryByText('Put in stock')).not.toBeInTheDocument();
  });

  test('fetches stocks when opened and displays the first stock', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    expect(getStocks).toHaveBeenCalled();
    expect(screen.getByText('Stock 1')).toBeInTheDocument();
  });

  test('adds a new row when "Add more" button is clicked', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    // Find and click the "Add more" button
    const addMoreButton = screen.getByText('Add more');
    await userEvent.click(addMoreButton);

    // Verify that another row is added (Stock 2 should be visible)
    expect(screen.getByText('Stock 2')).toBeInTheDocument();
  });

  test('removes a row when delete button is clicked', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    // Add a new row first
    const addMoreButton = screen.getByText('Add more');
    await userEvent.click(addMoreButton);

    // Find and click the delete button
    const deleteButtons = screen.getAllByTestId('DeleteOutlineIcon');
    await userEvent.click(deleteButtons[0]);

    // Verify that there's only one row left with Stock 2
    expect(screen.queryByText('Stock 1')).not.toBeInTheDocument();
    expect(screen.getByText('Stock 2')).toBeInTheDocument();
  });

  test('shows error when trying to save with no quantity', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    // Try to save with quantity 0
    const saveButton = screen.getByText('Save');
    await userEvent.click(saveButton);

    // Error message should be displayed
    expect(
      screen.getByText('At least one stock must have quantity greater than 0')
    ).toBeInTheDocument();
    expect(bulkAddStocks).not.toHaveBeenCalled();
  });

  test('opens confirm modal when valid data is entered', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    // Enter a valid quantity
    const quantityInput = screen.getByPlaceholderText('Quantity');
    await userEvent.clear(quantityInput);
    await userEvent.type(quantityInput, '10');

    // Click save button
    const saveButton = screen.getByText('Save');
    await userEvent.click(saveButton);

    // Confirm modal should be visible
    expect(screen.getByTestId('confirm-modal')).toHaveStyle('display: block');
    // Should contain 1 item
    expect(screen.getByTestId('stocks-count').textContent).toBe('1');
  });

  test('submits data to API when confirmed', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    // Enter a valid quantity
    const quantityInput = screen.getByPlaceholderText('Quantity');
    await userEvent.clear(quantityInput);
    await userEvent.type(quantityInput, '10');

    // Click save button to open confirm modal
    const saveButton = screen.getByText('Save');
    await userEvent.click(saveButton);

    // Click confirm button
    const confirmButton = screen.getByTestId('confirm-modal-button');
    await userEvent.click(confirmButton);

    // API should be called with correct data
    await waitFor(() => {
      expect(bulkAddStocks).toHaveBeenCalledWith({
        product_id: mockProduct.id,
        transfers: [
          {
            target_stock: 1,
            quantity_to_transfer: 10,
          },
        ],
      });
    });

    // Success toast should be shown
    expect(showToast).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Product added to stock(s) successfully',
      })
    );
  });

  test('handles API error', async () => {
    (bulkAddStocks as jest.Mock).mockRejectedValue(new Error('API error'));

    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    // Enter a valid quantity
    const quantityInput = screen.getByPlaceholderText('Quantity');
    await userEvent.clear(quantityInput);
    await userEvent.type(quantityInput, '10');

    // Click save button to open confirm modal
    const saveButton = screen.getByText('Save');
    await userEvent.click(saveButton);

    // Click confirm button
    const confirmButton = screen.getByTestId('confirm-modal-button');
    await userEvent.click(confirmButton);

    // Error should be displayed
    await waitFor(() => {
      expect(screen.getByText('Failed to update stocks')).toBeInTheDocument();
    });
  });

  test('closes the popup when close button is clicked', async () => {
    await act(async () => {
      render(
        <PutInStockPopup
          open={true}
          anchorEl={anchorEl}
          onClose={mockClose}
          onConfirm={mockConfirm}
          product={mockProduct}
        />
      );
    });

    const closeButton = screen.getByLabelText('close');
    await userEvent.click(closeButton);

    expect(mockClose).toHaveBeenCalled();
  });
});
