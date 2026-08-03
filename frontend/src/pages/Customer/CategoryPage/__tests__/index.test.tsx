import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProductsFilters from '../components/ProductsFilters';
import CategoryPage from '@pages/Customer/CategoryPage';
import { IProductPublic } from '../../../../types/products/interfaces';
import { PaginationProps } from '@mui/material';
import { getProductFiltersMeta } from '@services/http/public/products';

jest.mock('@pages/Customer/CategoryPage/hooks/useFilterProducts', () => () => ({
  products: [],
  page: 1,
  count: 0,
  priceMax: undefined,
  priceMin: undefined,
  setPage: jest.fn(),
  setFilters: jest.fn(),
  isLoading: false,
  deleteFilter: jest.fn(),
  ordering: undefined,
}));

jest.mock('../../../../hooks/useItemsPerPage', () => () => 10);
jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  useParams: () => ({ categoryId: '1' }),
  useOutletContext: () => ({ categories: [{ id: 1, name: 'Test Category' }] }),
}));

jest.mock(
  '@components/UI/customer/ProductCard',
  () =>
    ({ product }: { product: IProductPublic }) => (
      <div data-testid="product-card">{product.id}</div>
    )
);

jest.mock(
  '@components/UI/common/Pagination',
  () => (props: PaginationProps) => (
    <div data-testid="pagination">{props.page}</div>
  )
);
jest.mock('@services/http/public/products', () => ({
  getProductFiltersMeta: jest
    .fn()
    .mockResolvedValue({ minPrice: 5, maxPrice: 50 }),
}));

describe('CategoryPage', () => {
  test('renders title from params and context', async () => {
    render(
      <MemoryRouter initialEntries={['/category/1']}>
        <Routes>
          <Route path="/category/:categoryId" element={<CategoryPage />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(getProductFiltersMeta).toHaveBeenCalled());
    expect(screen.getByText('Test Category')).toBeInTheDocument();
  });

  test('shows "There are no products in the category yet" when no products and no filters', async () => {
    render(
      <MemoryRouter initialEntries={['/category/1']}>
        <Routes>
          <Route path="/category/:categoryId" element={<CategoryPage />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(getProductFiltersMeta).toHaveBeenCalled());
    expect(
      screen.getByText('There are no products in the category yet')
    ).toBeInTheDocument();
  });
});

describe('ProductsFilters', () => {
  const setFiltersMock = jest.fn();
  const deleteFilterMock = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders sort button and opens menu', async () => {
    render(
      <ProductsFilters
        priceMin={undefined}
        priceMax={undefined}
        ordering={undefined}
        setFilters={setFiltersMock}
        deleteFilter={deleteFilterMock}
      />
    );
    await waitFor(() => expect(getProductFiltersMeta).toHaveBeenCalled());
    const sortTrigger = screen.getByText(/Sort by price/i);
    expect(sortTrigger).toBeInTheDocument();
    fireEvent.click(sortTrigger);
    expect(screen.getByText('Lowest to Highest')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Lowest to Highest'));
    expect(setFiltersMock).toHaveBeenCalledWith({ ordering: 'price' });
  });

  test('displays price tag when min and max are set', async () => {
    render(
      <ProductsFilters
        priceMin={10}
        priceMax={20}
        ordering={undefined}
        setFilters={setFiltersMock}
        deleteFilter={deleteFilterMock}
      />
    );
    await waitFor(() => expect(getProductFiltersMeta).toHaveBeenCalled());
    expect(screen.getByText('From $10 to $20')).toBeInTheDocument();
    const closeButton = screen.getByTestId('CloseIcon');
    fireEvent.click(closeButton);
    expect(deleteFilterMock).toHaveBeenCalledWith('priceMax', 'priceMin');
  });
});
