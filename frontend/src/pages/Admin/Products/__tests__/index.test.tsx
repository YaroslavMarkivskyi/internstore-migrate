import { render, screen } from '@testing-library/react';
import AdminProducts from '../index';

// Mock the ProductsContent component
jest.mock('../components/ProductsContent', () => {
  return {
    __esModule: true,
    default: () => (
      <div data-testid="products-content">Mocked Products Content</div>
    ),
  };
});

describe('AdminProducts Page', () => {
  test('renders ProductsContent component', () => {
    render(<AdminProducts />);

    // Assert that ProductsContent is rendered
    const productsContent = screen.getByTestId('products-content');
    expect(productsContent).toBeInTheDocument();
    expect(productsContent).toHaveTextContent('Mocked Products Content');
  });
});
