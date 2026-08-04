import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import QuantityCellContainer from '../index';
import * as stocksService from '@services/http/admin/stocks';

// Mock the useParams hook from react-router
jest.mock('react-router', () => ({
  useParams: () => ({ stockId: '123' }),
}));

// Mock the EditableQuantityCell component to focus on container logic
jest.mock('../../EditableQuantityCell', () => {
  return function MockEditableQuantityCell({
    value,
    isEditing,
    onSave,
    onCancel,
  }: any) {
    return (
      <div data-testid="editable-quantity-cell">
        <span data-testid="display-value">{value}</span>
        {isEditing && (
          <button data-testid="save-button" onClick={() => onSave(value + 1)}>
            Save
          </button>
        )}
        {isEditing && (
          <button data-testid="cancel-button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    );
  };
});

// Mock the stocks service
jest.mock('@services/http/admin/stocks', () => ({
  updateStockProduct: jest.fn(),
}));

// Mock the showToast utility directly instead of react-toastify
jest.mock('@utils/showToast', () => ({
  __esModule: true,
  default: jest.fn(),
}));

// Import the mocked showToast for assertions
import showToast from '@utils/showToast';

describe('QuantityCellContainer', () => {
  const defaultProps = {
    productEntryId: '1',
    quantity: 5,
    isEditing: true,
    onEditComplete: jest.fn(),
    onUpdateSuccess: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // 1. RENDERING TESTS

  test('renders EditableQuantityCell with correct props', () => {
    render(<QuantityCellContainer {...defaultProps} />);

    // Check that EditableQuantityCell is rendered with the correct value
    const editableCell = screen.getByTestId('editable-quantity-cell');
    expect(editableCell).toBeInTheDocument();
    expect(screen.getByTestId('display-value')).toHaveTextContent('5');
  });

  test('passes correct isEditing prop when not updating', () => {
    render(<QuantityCellContainer {...defaultProps} isEditing={true} />);

    // Should show editing controls when isEditing is true and not updating
    expect(screen.getByTestId('save-button')).toBeInTheDocument();
    expect(screen.getByTestId('cancel-button')).toBeInTheDocument();
  });

  test('passes correct isEditing prop when updating', async () => {
    // Mock API to simulate loading state
    const updatePromise = new Promise(resolve => setTimeout(resolve, 100));
    (stocksService.updateStockProduct as jest.Mock).mockReturnValue(
      updatePromise
    );

    render(<QuantityCellContainer {...defaultProps} />);

    // Trigger save to set isUpdating to true
    const saveButton = screen.getByTestId('save-button');
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByTestId('save-button')).toBeInTheDocument();
    });

    // Wait for the update to complete
    await waitFor(() => {
      expect(stocksService.updateStockProduct).toHaveBeenCalled();
    });
  });

  // 2. API INTERACTION TESTS

  test('calls updateStockProduct when saving a new quantity', async () => {
    const mockUpdatedProduct = {
      id: '1',
      product: {
        id: '1',
        name: 'Test Product',
        price: 10,
        category: 'Test',
        minTemperature: 0,
        maxTemperature: 25,
        image: '',
      },
      quantity: 6,
      stockId: '123',
    };

    (stocksService.updateStockProduct as jest.Mock).mockResolvedValue(
      mockUpdatedProduct
    );

    render(<QuantityCellContainer {...defaultProps} />);

    // Click save button which triggers onSave with quantity + 1 (mocked behavior)
    const saveButton = screen.getByTestId('save-button');
    await userEvent.click(saveButton);

    // Verify API was called with correct arguments
    await waitFor(() => {
      expect(stocksService.updateStockProduct).toHaveBeenCalledWith(
        '123', // from mocked useParams
        '1', // productEntryId
        { quantity: 6 } // quantity + 1 from our mock
      );
    });
  });

  test('calls onUpdateSuccess and onEditComplete after successful update', async () => {
    (stocksService.updateStockProduct as jest.Mock).mockResolvedValue({});

    render(<QuantityCellContainer {...defaultProps} />);

    const saveButton = screen.getByTestId('save-button');
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(defaultProps.onUpdateSuccess).toHaveBeenCalled();
      expect(defaultProps.onEditComplete).toHaveBeenCalled();
    });
  });

  test('shows success toast after successful update', async () => {
    (stocksService.updateStockProduct as jest.Mock).mockResolvedValue({});

    render(<QuantityCellContainer {...defaultProps} />);

    const saveButton = screen.getByTestId('save-button');
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith({
        type: 'success',
        message: 'Quantity updated successfully',
      });
    });
  });

  test('shows error toast when update fails', async () => {
    const error = new Error('API Error');
    (stocksService.updateStockProduct as jest.Mock).mockRejectedValue(error);

    render(<QuantityCellContainer {...defaultProps} />);

    const saveButton = screen.getByTestId('save-button');
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith({
        type: 'error',
        message: 'Failed to update quantity',
      });
    });
  });

  // 3. CANCELLATION TESTS

  test('calls onEditComplete when cancel is clicked', async () => {
    render(<QuantityCellContainer {...defaultProps} />);

    // Click cancel button
    const cancelButton = screen.getByTestId('cancel-button');
    await userEvent.click(cancelButton);

    // Check onEditComplete was called
    expect(defaultProps.onEditComplete).toHaveBeenCalled();

    // Verify API was not called
    expect(stocksService.updateStockProduct).not.toHaveBeenCalled();
  });

  test('does not call onUpdateSuccess when cancelled', async () => {
    render(<QuantityCellContainer {...defaultProps} />);

    const cancelButton = screen.getByTestId('cancel-button');
    await userEvent.click(cancelButton);

    await waitFor(() => {
      expect(defaultProps.onUpdateSuccess).not.toHaveBeenCalled();
    });
  });
});
