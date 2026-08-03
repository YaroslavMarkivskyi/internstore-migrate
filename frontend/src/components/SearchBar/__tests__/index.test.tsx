import { act, fireEvent, screen, waitFor } from '@testing-library/react';

import { MAX_SEARCH_RESULTS_COUNT_DROPDOWN } from '@constants/search';
import { getProducts } from '@services/http/admin/products';
import MockSearchField from '../../UI/common/SearchField/__mocks__/index.mock';
import { SearchBar } from '../index';
import { renderWithRouter } from '@utils/testRenderWithRouter';

// Mock dependencies
jest.mock('@services/http/admin/products');
jest.mock('../../UI/common/SearchField', () => ({
  __esModule: true,
  default: MockSearchField,
}));

// Mock Redux hooks
const mockUseSelector = jest.fn();
const mockDispatch = jest.fn();
const mockUseDispatch = jest.fn(() => mockDispatch);

jest.mock('react-redux', () => ({
  ...jest.requireActual('react-redux'),
  useSelector: (selector: any) => mockUseSelector(selector),
  useDispatch: () => mockUseDispatch(),
}));

describe('SearchBar Component', () => {
  // Test fixtures
  const mockSearchHistory = [
    { query: 'laptop' },
    { query: 'monitor' },
    { query: 'keyboard' },
  ];

  const mockSearchResults = {
    count: 5,
    results: [
      {
        id: 1,
        name: 'Test Product 1',
        highlightedName: 'Test <b>Product</b> 1',
        price: '100.00',
        isPublished: true,
        totalQuantity: 50,
        mainImage: { image: 'test-image-1.jpg' },
      },
      {
        id: 2,
        name: 'Test Product 2',
        highlightedName: 'Test <b>Product</b> 2',
        price: '200.00',
        isPublished: true,
        totalQuantity: 25,
        mainImage: null,
      },
    ],
  };

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Mock Redux hooks implementation
    mockUseSelector.mockImplementation(selector => {
      // Mock state structure for selector
      const mockState = {
        searchHistory: {
          admin: mockSearchHistory,
          customer: [],
        },
      };
      return selector(mockState);
    });

    mockDispatch.mockClear();

    // Mock searchProducts API
    (getProducts as jest.Mock).mockResolvedValue(mockSearchResults);
  });

  test('renders correctly with initial state', () => {
    renderWithRouter(<SearchBar area={'admin'} />);

    // Check if SearchField is rendered
    expect(screen.getByTestId('search-field')).toBeInTheDocument();

    // Check if history items are passed correctly
    expect(screen.getByTestId('search-history')).toBeInTheDocument();
    expect(screen.getByTestId('history-item-0')).toHaveTextContent('laptop');
    expect(screen.getByTestId('history-item-1')).toHaveTextContent('monitor');
    expect(screen.getByTestId('history-item-2')).toHaveTextContent('keyboard');
  });

  test('performs search when input changes', async () => {
    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    const searchInput = screen.getByTestId('search-input');

    // Trigger search
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'product' } });
    });

    // Verify API was called with correct parameters
    expect(getProducts).toHaveBeenCalledWith({
      highlightMatches: true,
      search: 'product',
      limit: MAX_SEARCH_RESULTS_COUNT_DROPDOWN,
    });

    // Wait for results to be displayed
    await waitFor(() => {
      expect(screen.getByTestId('search-results')).toBeInTheDocument();
      expect(screen.getByTestId('product-1')).toBeInTheDocument();
      expect(screen.getByTestId('product-2')).toBeInTheDocument();
    });
  });

  test('adds search term to history when product is clicked', async () => {
    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    const searchInput = screen.getByTestId('search-input');

    // Search for something
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'product' } });
    });

    // Wait for results
    await waitFor(() => {
      expect(screen.getByTestId('search-results')).toBeInTheDocument();
    });

    // Click on a product
    fireEvent.click(screen.getByTestId('product-1'));

    // Verify dispatch was called with correct action
    expect(mockDispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: { query: 'product', area: 'admin' },
        type: expect.any(String),
      })
    );
  });

  test('removes history item when delete button is clicked', async () => {
    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    // Click delete on first history item
    fireEvent.click(screen.getByTestId('delete-history-0'));

    // Verify dispatch was called with correct action
    expect(mockDispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: { query: 'laptop', area: 'admin' },
        type: expect.any(String),
      })
    );
  });

  test('clears all history when clear button is clicked', async () => {
    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    // Click clear history button
    fireEvent.click(screen.getByTestId('clear-history'));

    // Verify dispatch was called with correct action
    expect(mockDispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: { area: 'admin' },
        type: expect.any(String),
      })
    );
  });

  test('clicking on history item performs search for that term', async () => {
    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    // Click on a history item
    await act(async () => {
      fireEvent.click(screen.getByTestId('history-item-1')); // "monitor"
    });

    // Verify search was performed with correct term
    expect(getProducts).toHaveBeenCalledWith(
      expect.objectContaining({
        search: 'monitor',
      })
    );

    // Verify item was added to history (bringing it to the top)
    expect(mockDispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: { query: 'monitor', area: 'admin' },
        type: expect.any(String),
      })
    );

    // Wait for results to update
    await waitFor(() => {
      expect(screen.getByTestId('search-results')).toBeInTheDocument();
    });
  });

  test('shows "show all results" button when there are more results than the limit', async () => {
    // Set up mock to return more results than the limit
    (getProducts as jest.Mock).mockResolvedValue({
      count: MAX_SEARCH_RESULTS_COUNT_DROPDOWN + 2, // More than the limit
      results: mockSearchResults.results,
    });

    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    const searchInput = screen.getByTestId('search-input');

    // Search for something
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'product' } });
    });

    // Wait for the "show all results" button to appear
    await waitFor(() => {
      expect(screen.getByTestId('show-all-results')).toBeInTheDocument();
    });

    // Click the button
    fireEvent.click(screen.getByTestId('show-all-results'));

    // Verify dispatch was called with correct action
    expect(mockDispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: { query: 'product', area: 'admin' },
        type: expect.any(String),
      })
    );
  });

  test('handles error during search', async () => {
    // Mock API to throw an error
    (getProducts as jest.Mock).mockRejectedValue(new Error('API error'));

    // Mock console.error to avoid cluttering test output
    const originalConsoleError = console.error;
    console.error = jest.fn();

    await act(async () => {
      renderWithRouter(<SearchBar area={'admin'} />);
    });

    const searchInput = screen.getByTestId('search-input');

    // Trigger search that will fail
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'error-trigger' } });
    });

    // Verify console.error was called
    expect(console.error).toHaveBeenCalled();

    // Verify no results are shown after error
    expect(screen.queryByTestId('search-results')).not.toBeInTheDocument();

    // Restore console.error
    console.error = originalConsoleError;
  });
});
