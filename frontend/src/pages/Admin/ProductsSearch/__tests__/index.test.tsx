import { screen, fireEvent } from '@testing-library/react';
import AdminProductsSearch from '../';
import { renderWithRouter } from '@utils/testRenderWithRouter';
import React from 'react';
import useFilterProducts from '../../../../hooks/useFilterProducts';

// Mocks
const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

jest.mock('../../../../hooks/useFilterProducts');

const mockedUseSearchBarProducts = useFilterProducts as jest.Mock;

jest.mock(
  '../../Products/components/ProductsContent/components/ProductsFilterTag',
  () => () => (
    <div
      data-testid="products-filter-tag"
      onClick={() => mockNavigate('/admin/products')}
    >
      Tag
    </div>
  )
);

jest.mock(
  '../../Products/components/ProductsContent/components/ProductsPagination',
  () => ({
    __esModule: true,
    default: ({ count }: any) => (
      <div data-testid="products-pagination">Pagination: {count} pages</div>
    ),
  })
);

jest.mock(
  '../../Products/components/ProductsContent/components/ProductsTable',
  () => () => <div data-testid="products-table">Table of Products</div>
);

jest.mock('../../Products/components/ProductsContent/styles', () => ({
  ProductsContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock(
  '../../Products/components/ProductsContent/components/ProductsFilters/styles',
  () => ({
    TagsWrapper: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    ),
  })
);

jest.mock('../styles', () => ({
  NotFoundTitle: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="not-found-title">{children}</div>
  ),
  SearchTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

describe('AdminProductsSearch', () => {
  beforeEach(() => {
    // Default mock
    mockedUseSearchBarProducts.mockReturnValue({
      products: Array(8)
        .fill(null)
        .map((_, i) => ({ id: i, name: `Product ${i}` })),
      count: 24,
      page: 1,
      limit: 8,
      search: 'test',
      setPage: jest.fn(),
      setFilters: jest.fn(),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders result when products are found', () => {
    renderWithRouter(<AdminProductsSearch />);

    expect(screen.getByText('24 results found')).toBeInTheDocument();
    expect(screen.getByTestId('products-filter-tag')).toBeInTheDocument();
    expect(screen.getByTestId('products-table')).toBeInTheDocument();
    expect(screen.getByTestId('products-pagination')).toHaveTextContent(
      'Pagination: 3 pages'
    );
  });

  test('navigates back to product list on tag click', () => {
    renderWithRouter(<AdminProductsSearch />);
    fireEvent.click(screen.getByTestId('products-filter-tag'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin/products');
  });

  test('renders NotFoundTitle when no searchTerm or count is 0', () => {
    mockedUseSearchBarProducts.mockReturnValueOnce({
      products: [],
      count: 0,
      page: 1,
      limit: 8,
      search: '',
      setPage: jest.fn(),
      setFilters: jest.fn(),
    });

    renderWithRouter(<AdminProductsSearch />);
    expect(screen.getByTestId('not-found-title')).toBeInTheDocument();
  });
});
