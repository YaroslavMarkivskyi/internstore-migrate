import { render, fireEvent, act } from '@testing-library/react';
import QuantityInput from '../';
import { CartProvider } from '../../../../../../../hooks/useCart';

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

describe('QuantityInput', () => {
  jest.useFakeTimers();

  const defaultProps = {
    defaultValue: 2,
    onChange: jest.fn(),
    productPrice: '10.00',
  };

  it('renders initial value and buttons', () => {
    const { getByDisplayValue, getByTestId } = render(
      <CartProvider>
        <QuantityInput {...defaultProps} />
      </CartProvider>
    );
    expect(getByDisplayValue('2')).toBeInTheDocument();
    expect(getByTestId('+quantity')).toBeEnabled();
    expect(getByTestId('-quantity')).toBeEnabled();
  });

  it('increments and triggers onChange after debounce', () => {
    const { getByTestId, getByDisplayValue } = render(
      <CartProvider>
        <QuantityInput {...defaultProps} />
      </CartProvider>
    );
    const incrementBtn = getByTestId('+quantity');
    act(() => {
      fireEvent.click(incrementBtn);
      jest.advanceTimersByTime(1200);
    });
    expect(getByDisplayValue('3')).toBeInTheDocument();
    expect(defaultProps.onChange).toHaveBeenCalledWith(3);
  });

  it('decrements and does not go below min', () => {
    const props = { ...defaultProps, defaultValue: 1 };
    const { getByTestId, getByDisplayValue } = render(
      <CartProvider>
        <QuantityInput {...props} />
      </CartProvider>
    );
    const decrementBtn = getByTestId('-quantity');
    fireEvent.click(decrementBtn);
    expect(getByDisplayValue('1')).toBeInTheDocument();
  });
});
