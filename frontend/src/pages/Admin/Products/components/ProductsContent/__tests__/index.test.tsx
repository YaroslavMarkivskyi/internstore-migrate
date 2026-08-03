import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import MockSelectFieldAdmin from '@components/UI/admin/SelectFieldAdmin/__mocks__/SelectFieldAdmin.mock';
import MockCategorySelect from '@components/CategorySelect/__mocks__/CategorySelect.mock';
import ProductsTable from '../components/ProductsTable';
import { ICategory } from '../../../../../../types/categories/interfaces';
import { IProductAdmin } from '../../../../../../types/products/interfaces';
import ProductsContent from '..';
import { useSelector } from '@store/store';
import ProductsFilters from '../components/ProductsFilters';
import useFilterProducts from '../../../../../../hooks/useFilterProducts';
import { renderWithRouter } from '@utils/testRenderWithRouter';
import { getProductFiltersMeta } from '@services/http/admin/products';
import userEvent from '@testing-library/user-event';

// Mocks
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

jest.mock('../../../../../../hooks/useFilterProducts', () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock('@components/UI/admin/IOSSwitch', () => ({
  __esModule: true,
  default: ({ checked, onChange }: any) => (
    <input
      data-testid="ios-switch"
      type="checkbox"
      checked={checked}
      onChange={onChange}
    />
  ),
}));
jest.mock('../components/ProductsMenuPopup', () => ({
  __esModule: true,
  default: ({ product }: any) => (
    <div data-testid={`menu-popup-${product.id}`} />
  ),
}));

jest.mock('@components/CategorySelect', () => ({
  __esModule: true,
  default: MockCategorySelect,
}));

jest.mock('@components/UI/admin/SelectFieldAdmin', () => ({
  __esModule: true,
  default: MockSelectFieldAdmin,
}));

// Mock Redux selector and service
jest.mock('@store/store', () => ({
  __esModule: true,
  useSelector: jest.fn(),
}));

jest.mock('@services/http/admin/products', () => ({
  __esModule: true,
  getProductFiltersMeta: jest.fn().mockResolvedValue({
    minPrice: 0,
    maxPrice: 100,
    minQuantity: 0,
    maxQuantity: 50,
  }),
}));

const mockSetFilters = jest.fn();
const mockSetPage = jest.fn();
const mockDeleteFilter = jest.fn();
const mockSetProducts = jest.fn();

describe('ProductsTable', () => {
  const categories: ICategory[] = [
    { name: 'Category 1', id: '1' },
    { name: 'Category 2', id: '2' },
    { name: 'Category 3', id: '3' },
  ];

  const sampleProducts: IProductAdmin[] = [
    {
      id: '101',
      name: 'Sparkling Water',
      price: '1.99',
      minTemperature: 2,
      maxTemperature: 8,
      category: categories[0],
      description: 'Refreshing carbonated water with a hint of lemon.',
      isPublished: true,
      image: 'https://example.com/images/sparkling-water.png',
      totalQuantity: 120,
    },
    {
      id: '102',
      name: 'Organic Almonds',
      price: '5.49',
      minTemperature: 10,
      maxTemperature: 25,
      category: categories[1],
      description: 'Raw organic almonds, perfect for snacking.',
      isPublished: false,
      // no image provided, will fall back to placeholder
      totalQuantity: 75,
    },
    {
      id: '103',
      name: 'Ripe Bananas',
      price: '0.59',
      minTemperature: 12,
      maxTemperature: 18,
      category: categories[2],
      description: 'Freshly harvested bananas, sold per piece.',
      isPublished: true,
      image: 'https://example.com/images/bananas.png',
      totalQuantity: 200,
    },
  ];
  const setOrdering = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders table headers and rows', () => {
    render(
      <ProductsTable
        products={sampleProducts}
        setOrdering={setOrdering}
        setProducts={mockSetProducts}
      />
    );
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('Image')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Price')).toBeInTheDocument();
    expect(screen.getByText('Quantity')).toBeInTheDocument();
    expect(screen.getByText('Published')).toBeInTheDocument();
    expect(screen.getByText('Sparkling Water')).toBeInTheDocument();
    expect(screen.getByText('Category 1')).toBeInTheDocument();
    expect(screen.getByText('1.99')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getAllByTestId('ios-switch').length).toBeGreaterThan(0);
    expect(screen.getByTestId('menu-popup-101')).toBeInTheDocument();
  });

  test('sort buttons call setOrdering', async () => {
    render(
      <ProductsTable
        products={sampleProducts}
        setOrdering={setOrdering}
        setProducts={mockSetProducts}
      />
    );
    const sortButtons = screen.getAllByRole('button');
    await userEvent.click(sortButtons[0]);
    expect(setOrdering).toHaveBeenCalledWith('price');
    await userEvent.click(sortButtons[1]);
    expect(setOrdering).toHaveBeenCalledWith('total_quantity');
  });
});

describe('ProductsFilters', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders all filter controls and fetches metadata', async () => {
    const categoriesMock = ['Cat1', 'Cat2'];
    (useSelector as jest.Mock).mockReturnValue(categoriesMock);
    await act(async () => {
      renderWithRouter(
        <ProductsFilters
          setFilters={mockSetFilters}
          deleteFilter={mockDeleteFilter}
          priceMin={10}
          priceMax={20}
          totalQuantityMin={5}
          totalQuantityMax={15}
          category={['1']}
          isPublished={true}
        />
      );
    });
    const catSelect = screen.getByTestId('category-input');
    expect(catSelect).toBeInTheDocument();
    expect(
      screen.getAllByText('Published and Unpublished').length
    ).toBeGreaterThan(0);
    expect(screen.getAllByText('$10 - $20').length).toBeGreaterThan(0);
    expect(screen.getAllByText('5 - 15').length).toBeGreaterThan(0);

    expect(getProductFiltersMeta).toHaveBeenCalled();
  });

  test('category change calls setFilters', async () => {
    (useSelector as jest.Mock).mockReturnValue(['Cat1', 'Cat2']);
    await act(async () =>
      renderWithRouter(
        <ProductsFilters
          setFilters={mockSetFilters}
          deleteFilter={mockDeleteFilter}
          category={[]}
        />
      )
    );
    const catSelect = screen.getByTestId('category-input');
    await userEvent.selectOptions(catSelect, ['1']);
    expect(mockSetFilters).toHaveBeenCalledWith({ category: '1' });
  });

  test('publish change toggles filters correctly', async () => {
    (useSelector as jest.Mock).mockReturnValue(['Cat1', 'Cat2']);
    await act(async () =>
      renderWithRouter(
        <ProductsFilters
          setFilters={mockSetFilters}
          deleteFilter={mockDeleteFilter}
        />
      )
    );
    const publishSelect = screen.getByTestId('published-input');
    await userEvent.selectOptions(publishSelect, ['Published']);
    expect(mockSetFilters).toHaveBeenCalledWith({ isPublished: true });
  });
});

describe('ProductsContent', () => {
  const mockHook = useFilterProducts as jest.MockedFunction<
    typeof useFilterProducts
  >;
  const defaultHook = {
    products: [
      {
        id: 1,
        name: 'P',
        image: '',
        category: 'C',
        price: 0,
        totalQuantity: 0,
        isPublished: false,
      },
    ],
    count: 30,
    ordering: 'price',
    page: 1,
    priceMin: undefined,
    priceMax: undefined,
    totalQuantityMin: undefined,
    totalQuantityMax: undefined,
    category: undefined,
    isPublished: undefined,
    setFilters: mockSetFilters,
    deleteFilter: mockDeleteFilter,
    setPage: mockSetPage,
    isLoading: false,
  };

  beforeEach(() => {
    mockHook.mockReturnValue(defaultHook as any);
    jest.clearAllMocks();
  });

  test('renders header, filters, table and pagination', async () => {
    await act(async () => renderWithRouter(<ProductsContent />));
    expect(screen.getAllByText('Price').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Quantity').length).toBeGreaterThan(0);
    expect(screen.getByText('P')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /1/ })).toBeInTheDocument();
  });

  test('shows loader when loading', async () => {
    mockHook.mockReturnValue({ ...defaultHook, isLoading: true } as any);
    await act(async () => renderWithRouter(<ProductsContent />));
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('pagination change', async () => {
    await act(async () => renderWithRouter(<ProductsContent />));
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    expect(mockSetPage).toHaveBeenCalledWith(2);
  });

  test('ordering toggle', async () => {
    await act(async () => renderWithRouter(<ProductsContent />));
    const priceSortBtn = screen.getByTestId('sort-price');
    await userEvent.click(priceSortBtn);
    expect(mockSetFilters).toHaveBeenCalledWith({ ordering: '-price' });
    const quantitySortBtn = screen.getByTestId('sort-quantity');
    await userEvent.click(quantitySortBtn);
    expect(mockSetFilters).toHaveBeenCalledWith({ ordering: 'total_quantity' });
  });
});
