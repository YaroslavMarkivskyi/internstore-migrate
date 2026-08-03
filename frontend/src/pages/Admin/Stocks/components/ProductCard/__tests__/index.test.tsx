import { act, render, screen, waitFor } from '@testing-library/react';
import { getProduct, getStocksDetails } from '@services/http/admin/products';
import { imagePlaceholderUrl } from '@constants/urls';
import ProductCard from '@pages/Admin/Stocks/components/ProductCard';

// Mocks
jest.mock('quill', () => {
  return jest.fn().mockImplementation(() => ({
    on: jest.fn(),
    getContents: jest.fn(),
    setContents: jest.fn(),
    root: { innerHTML: '' },
    clipboard: { convert: jest.fn() },
    setText: jest.fn(),
    getText: jest.fn(),
  }));
});

jest.mock('@services/http/admin/products', () => ({
  __esModule: true,
  getProduct: jest.fn(),
  getStocksDetails: jest.fn(),
}));

describe('ProductCard', () => {
  const mockProduct = {
    id: 1,
    name: 'Test Product',
    image: '',
    minTemperature: 5,
    maxTemperature: 10,
  };

  const mockStocks = [
    {
      id: '1',
      name: 'Stock A',
      quantity: 100,
      temperature: 12,
      humidity: 0.55,
    },
    {
      id: '2',
      name: 'Stock B',
      quantity: 80,
      temperature: 7,
      humidity: 0.65,
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    (getProduct as jest.Mock).mockResolvedValue(mockProduct);
    (getStocksDetails as jest.Mock).mockResolvedValue({ stocks: mockStocks });
  });

  test('renders loader initially', async () => {
    render(<ProductCard selectedProductId={1} />);
    await act(async () => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  test('renders product name and image', async () => {
    render(<ProductCard selectedProductId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Test Product')).toBeInTheDocument();
    });

    const image = screen.getByAltText('Product') as HTMLImageElement;
    expect(image).toHaveAttribute('src', imagePlaceholderUrl);
  });

  test('renders stock details rows', async () => {
    render(<ProductCard selectedProductId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Stock A')).toBeInTheDocument();
      expect(screen.getByText('Stock B')).toBeInTheDocument();
    });

    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByText('12.00')).toBeInTheDocument();
    expect(screen.getByText('7.00')).toBeInTheDocument();
    expect(screen.getByText('55.00%')).toBeInTheDocument();
    expect(screen.getByText('65.00%')).toBeInTheDocument();
  });

  test('applies error class to temperature out of range', async () => {
    render(<ProductCard selectedProductId={1} />);
    await waitFor(() => {
      const errorCells = screen
        .getAllByText('Stock A')[0]
        .closest('tr')
        ?.querySelectorAll('.error');
      expect(errorCells?.length).toBeGreaterThan(0);
    });
  });

  test('does not render without selectedProductId', async () => {
    await act(async () => {
      const { container } = render(
        <ProductCard selectedProductId={undefined} />
      );
      expect(container.firstChild).toBeNull();
    });
  });
});
