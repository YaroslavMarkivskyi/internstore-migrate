import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EditableQuantityCell from '../index';

// Mock the styles module to avoid issues with styled components during testing
jest.mock('../styles', () => ({
  StyledQuantityInput: ({ children, ...props }: any) => (
    <input data-testid="styled-quantity-input" {...props}>
      {children}
    </input>
  ),
}));

describe('EditableQuantityCell', () => {
  // Mock handlers that we'll use throughout tests
  const mockOnSave = jest.fn();
  const mockOnCancel = jest.fn();

  beforeEach(() => {
    // Clear mocks before each test
    jest.clearAllMocks();
  });

  // 1. RENDERING TESTS

  test('renders display mode with correct value', () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={false}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    // Verify that the component shows the value as text
    expect(screen.getByText('5')).toBeInTheDocument();
    // Verify that the input is not in the document
    expect(
      screen.queryByTestId('styled-quantity-input')
    ).not.toBeInTheDocument();
  });

  test('renders edit mode with input field', () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    // Verify that the input is in the document
    const input = screen.getByTestId('styled-quantity-input');
    expect(input).toBeInTheDocument();
    // Verify that the input has the correct value
    expect(input).toHaveValue('5');
  });

  test('adjusts input width based on value length', () => {
    render(
      <EditableQuantityCell
        value={1000}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');
    // The width should be based on the length of "1000" which is 4 characters
    expect(input).toHaveStyle('width: 4ch');
  });

  // 2. INPUT HANDLING TESTS

  test('allows changing input value', async () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Clear the input and type a new value
    await userEvent.clear(input);
    await userEvent.type(input, '10');

    // Verify that the input has the new value
    expect(input).toHaveValue('10');
  });

  test('validates input to only allow numeric values', async () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Try typing non-numeric characters
    await userEvent.clear(input);
    await userEvent.type(input, 'abc');

    // Input should still have its original value since non-numeric input is rejected
    expect(input).toHaveValue('');

    // Now try with valid numeric input
    await userEvent.type(input, '123');
    expect(input).toHaveValue('123');
  });

  // 3. KEYBOARD INTERACTION TESTS

  test('saves value when Enter key is pressed with valid input', () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Change the value and press Enter
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // Verify that onSave was called with the new value
    expect(mockOnSave).toHaveBeenCalledWith(10);
    expect(mockOnCancel).not.toHaveBeenCalled();
  });

  test('cancels when Enter key is pressed with invalid input', () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Set to an empty string (invalid) and press Enter
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // Verify that onCancel was called instead of onSave
    expect(mockOnSave).not.toHaveBeenCalled();
    expect(mockOnCancel).toHaveBeenCalled();
  });

  test('cancels and resets value when Escape key is pressed', () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Change the value and press Escape
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.keyDown(input, { key: 'Escape' });

    // Verify that onCancel was called and onSave was not
    expect(mockOnCancel).toHaveBeenCalled();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  // 4. EVENT HANDLER TESTS

  test('cancels when input loses focus', () => {
    render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Change the value and trigger blur event
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.blur(input);

    // Verify that onCancel was called
    expect(mockOnCancel).toHaveBeenCalled();
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  test('resets input value to original when props change', async () => {
    const { rerender } = render(
      <EditableQuantityCell
        value={5}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    const input = screen.getByTestId('styled-quantity-input');

    // Change the input value
    fireEvent.change(input, { target: { value: '10' } });
    expect(input).toHaveValue('10');

    // Rerender with new props
    rerender(
      <EditableQuantityCell
        value={20}
        isEditing={true}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );

    // Input value should be updated to match the new props
    await waitFor(() => {
      expect(input).toHaveValue('20');
    });
  });
});
