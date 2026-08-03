import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { act } from 'react';

import MoveToStockMenu from '../index';
import * as stocksService from '@services/http/admin/stocks';
import showToast from '@utils/showToast';
import * as validationModule from '../validation';
import { TransferItemProps } from '../components/TransferItem';
import { AddDestinationButtonProps } from '../components/AddDestinationBtn';
import { CancelButtonProps } from '../components/CancelButton';
import { SaveButtonProps } from '../components/SaveButton';
import { IStockProduct } from '../../../../../../types/stocks/interfaces';

// Mock the services and utilities
jest.mock('@services/http/admin/stocks', () => ({
  getStock: jest.fn(),
  getStocks: jest.fn(),
  distributeProducts: jest.fn(),
}));

jest.mock('@utils/showToast', () => ({
  __esModule: true,
  default: jest.fn(options => {
    // Immediately invoke onClose to simulate toast autoClose
    if (options.onClose) options.onClose();
  }),
}));

// Mock the child components
jest.mock('../components/TransferItem', () => {
  return {
    __esModule: true,
    default: ({
      availableStocks,
      quantity,
      selectedStockId,
      onQuantityChange,
      onStockChange,
    }: TransferItemProps) => (
      <div data-testid="transfer-item">
        <select
          data-testid="stock-select"
          value={selectedStockId || ''}
          onChange={e => onStockChange(Number(e.target.value) || null)}
        >
          <option value="">Select Stock</option>
          {availableStocks.map(stock => (
            <option key={stock.id} value={stock.id}>
              {stock.name}
            </option>
          ))}
        </select>
        <input
          data-testid="quantity-input"
          type="number"
          value={quantity}
          onChange={e => onQuantityChange(Number(e.target.value))}
          disabled={!selectedStockId}
        />
      </div>
    ),
  };
});

jest.mock('../components/AddDestinationBtn', () => {
  return {
    __esModule: true,
    default: ({ onClick }: AddDestinationButtonProps) => (
      <button data-testid="add-destination-btn" onClick={onClick}>
        Add a stock
      </button>
    ),
  };
});

// Add mocks for CancelButton and SaveButton
jest.mock('../components/CancelButton', () => {
  return {
    __esModule: true,
    default: ({ onClick, isDisabled }: CancelButtonProps) => (
      <button
        data-testid="button-cancel"
        onClick={onClick}
        disabled={isDisabled}
      >
        Cancel
      </button>
    ),
  };
});

jest.mock('../components/SaveButton', () => {
  return {
    __esModule: true,
    default: ({ onClick, isDisabled }: SaveButtonProps) => (
      <button data-testid="button-save" onClick={onClick} disabled={isDisabled}>
        Save
      </button>
    ),
  };
});

// Mock the styled components
jest.mock('../styles', () => ({
  StyledMoveToStockContainer: ({
    children,
  }: {
    children?: React.ReactNode;
  }) => <div data-testid="move-to-stock-container">{children}</div>,
  StyledMoveToStockCloseButton: ({ onClick }: { onClick?: () => void }) => (
    <button data-testid="close-button" onClick={onClick}>
      Close
    </button>
  ),
  MoveToStockTitle: ({ children }: { children?: React.ReactNode }) => (
    <h2 data-testid="move-to-stock-title">{children}</h2>
  ),
  MoveToStockText: ({ children }: { children?: React.ReactNode }) => (
    <span data-testid="move-to-stock-text">{children}</span>
  ),
  MoveFromInput: ({
    value,
    disabled,
  }: {
    value?: string;
    disabled?: boolean;
  }) => (
    <input
      data-testid="move-from-input"
      value={value || ''}
      disabled={disabled}
      readOnly
    />
  ),
  QuantityInput: ({
    value,
    disabled,
  }: {
    value?: number;
    disabled?: boolean;
  }) => (
    <input
      data-testid="source-quantity-input"
      type="number"
      value={value || 0}
      disabled={disabled}
      readOnly
    />
  ),
  TargetStockSelect: ({ value, onChange, options }: any) => (
    <select
      data-testid="target-stock-select"
      value={value || ''}
      onChange={e => onChange(e)}
    >
      <option value="">Select Stock</option>
      {options?.map((option: any) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
  AddDestinationStockIcon: ({ children }: { children?: React.ReactNode }) => (
    <span data-testid="add-destination-icon">{children}</span>
  ),
}));

// Mock ErrorText component
jest.mock('@components/auth/styles', () => ({
  ErrorText: ({
    children,
    color,
  }: {
    children?: React.ReactNode;
    color?: string;
  }) => (
    <div data-testid="error-text" data-color={color}>
      {children}
    </div>
  ),
}));

// We don't need this mock anymore since we're mocking CancelButton and SaveButton directly
jest.mock('@components/UI/admin/ButtonAdmin', () => {
  return {
    __esModule: true,
    default: ({ children, onClick, disabled }: any) => (
      <button onClick={onClick} disabled={disabled}>
        {children}
      </button>
    ),
  };
});

describe('MoveToStockMenu Component', () => {
  // Sample test data
  const mockSourceStock = { id: 2, name: 'Warehouse A' };
  const mockStocks = [
    { id: 1, name: 'Store B' },
    { id: 3, name: 'Store C' },
    { id: 4, name: 'Store D' },
  ];
  const mockProductStockEntry: IStockProduct = {
    id: 4,
    quantity: 10,
    stockId: 2,
    product: {
      id: 1,
      image: 'product-image.jpg',
      name: 'Test Product',
      category: 'bars',
      price: 10.99,
      minTemperature: -10,
      maxTemperature: 20,
    },
  };

  const defaultProps = {
    sourceStockId: 2,
    productStockEntry: mockProductStockEntry,
    onClose: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock implementations
    (stocksService.getStock as jest.Mock).mockResolvedValue(mockSourceStock);
    (stocksService.getStocks as jest.Mock).mockResolvedValue([
      mockSourceStock,
      ...mockStocks,
    ]);
    (stocksService.distributeProducts as jest.Mock).mockResolvedValue({
      success: true,
    });
  });

  test('renders correctly with initial state', async () => {
    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Check if the component renders correctly
    expect(screen.getByTestId('move-to-stock-title')).toHaveTextContent(
      'Move to stock'
    );
    expect(screen.getByTestId('close-button')).toBeInTheDocument();

    // Check if it's fetching the stocks on mount
    expect(stocksService.getStock).toHaveBeenCalledWith(
      defaultProps.sourceStockId
    );
    expect(stocksService.getStocks).toHaveBeenCalled();

    // Check if source stock info is displayed correctly
    await waitFor(() => {
      expect(screen.getByTestId('move-from-input')).toHaveValue('Warehouse A');
      expect(screen.getByTestId('source-quantity-input')).toHaveValue(10);
    });

    // Check if initial transfer item is displayed
    expect(screen.getByTestId('transfer-item')).toBeInTheDocument();

    // Check if action buttons are displayed
    expect(screen.getByTestId('button-cancel')).toBeInTheDocument();
    expect(screen.getByTestId('button-save')).toBeInTheDocument();
  });

  test('adds a new transfer item when add button is clicked', async () => {
    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Initial state should have one transfer item
    expect(screen.getAllByTestId('transfer-item').length).toBe(1);

    // Click add button
    const addButton = screen.getByTestId('add-destination-btn');
    fireEvent.click(addButton);

    // Should have two transfer items now
    expect(screen.getAllByTestId('transfer-item').length).toBe(2);
  });

  test('handles stock selection and quantity change', async () => {
    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Select a stock in the first transfer item
    const stockSelect = screen.getByTestId('stock-select');
    fireEvent.change(stockSelect, { target: { value: '1' } });

    // Change quantity
    const quantityInput = screen.getByTestId('quantity-input');
    fireEvent.change(quantityInput, { target: { value: '5' } });

    // Save the changes
    const saveButton = screen.getByTestId('button-save');
    fireEvent.click(saveButton);

    // Check if distributeProducts was called with correct data
    await waitFor(() => {
      expect(stocksService.distributeProducts).toHaveBeenCalledWith(
        { transfers: [{ targetStock: 1, quantityToTransfer: 5 }] },
        2,
        4
      );
    });

    // Check if onClose was called
    await waitFor(() => {
      expect(defaultProps.onClose).toHaveBeenCalled();
    });

    // Check if success toast was shown
    expect(showToast).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Saved successfully',
        type: 'success',
      })
    );
  });

  test('validates transfers before saving', async () => {
    // Spy on validation function
    const validateSpy = jest.spyOn(validationModule, 'validateTransfers');
    validateSpy.mockReturnValue('Validation error message');

    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Try to save
    const saveButton = screen.getByTestId('button-save');
    fireEvent.click(saveButton);

    // Check if validation was called
    expect(validateSpy).toHaveBeenCalled();

    // Check if error message is displayed
    expect(screen.getByTestId('error-text')).toHaveTextContent(
      'Validation error message'
    );

    // distributeProducts should not be called if validation fails
    expect(stocksService.distributeProducts).not.toHaveBeenCalled();

    // Reset the mock
    validateSpy.mockRestore();
  });

  test('handles API errors during save', async () => {
    // Mock distributeProducts to reject with error
    (stocksService.distributeProducts as jest.Mock).mockRejectedValue(
      new Error('API Error')
    );

    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Select a stock
    const stockSelect = screen.getByTestId('stock-select');
    fireEvent.change(stockSelect, { target: { value: '1' } });

    // Set quantity
    const quantityInput = screen.getByTestId('quantity-input');
    fireEvent.change(quantityInput, { target: { value: '5' } });

    // Temporarily mock validateTransfers to return null (no errors)
    const validateSpy = jest.spyOn(validationModule, 'validateTransfers');
    validateSpy.mockReturnValue(null);

    // Try to save
    const saveButton = screen.getByTestId('button-save');
    fireEvent.click(saveButton);

    // Wait for API call to fail
    await waitFor(() => {
      expect(stocksService.distributeProducts).toHaveBeenCalled();
    });

    // Check if error message is displayed
    expect(screen.getByTestId('error-text')).toHaveTextContent(
      'An error occurred while saving'
    );

    // onClose should not be called on error
    expect(defaultProps.onClose).not.toHaveBeenCalled();

    // Reset the mock
    validateSpy.mockRestore();
  });

  test('handles cancel button click', async () => {
    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Click cancel button
    const cancelButton = screen.getByTestId('button-cancel');
    fireEvent.click(cancelButton);

    // Check if onClose was called
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  test('shows add destination button only when there are available stocks', async () => {
    (stocksService.getStocks as jest.Mock).mockResolvedValue([mockSourceStock]);

    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    await waitFor(() => {
      expect(
        screen.queryByTestId('add-destination-btn')
      ).not.toBeInTheDocument();
    });
  });

  test('handles API errors during stocks fetch', async () => {
    const originalConsoleError = console.error;
    console.error = jest.fn(); // Suppress console.error for this test

    // Mock API error
    (stocksService.getStock as jest.Mock).mockRejectedValue(
      new Error('Failed to fetch')
    );

    await act(async () => {
      render(<MoveToStockMenu {...defaultProps} />);
    });

    // Component should still render without crashing
    expect(screen.getByTestId('move-to-stock-container')).toBeInTheDocument();

    // Console error should have been called
    expect(console.error).toHaveBeenCalled();

    // Restore console.error
    console.error = originalConsoleError;
  });
});
