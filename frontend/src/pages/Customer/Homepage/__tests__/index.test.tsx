import { fireEvent, screen } from '@testing-library/react';
import { imagePlaceholderUrl } from '@constants/urls';
import { Provider } from 'react-redux';
import Homepage from '../index';
import { renderWithRouter } from '@utils/testRenderWithRouter';
import * as ReactRouter from 'react-router';
import { ReactNode } from 'react';
import { configureStore } from '@reduxjs/toolkit';

const mockCategories = [
  { id: 1, name: 'Alpha', image: 'http://img.alpha' },
  { id: 2, name: 'Beta', image: '' },
];

const mockNavigate = jest.fn();

jest.mock('react-router', () => {
  const actual = jest.requireActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useOutletContext: jest.fn(),
  };
});

const createMockStore = (preloadedState: any) =>
  configureStore({
    reducer: (state = preloadedState, _action) => state,
    middleware: getDefaultMiddleware =>
      getDefaultMiddleware({ serializableCheck: false }),
  });

const mockInitialState = {
  recentProducts: {
    productIds: [],
  },
  category: {},
  auth: {},
  searchHistory: {},
};

const renderWithMockStore = (ui: ReactNode, state = mockInitialState) => {
  const store = createMockStore(state);
  return renderWithRouter(<Provider store={store}>{ui}</Provider>);
};

jest.mock('react-router', () => {
  const actual = jest.requireActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useOutletContext: jest.fn(),
  };
});

describe('Homepage component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (ReactRouter.useOutletContext as jest.Mock).mockReturnValue({
      categories: mockCategories,
    });
  });

  test('renders catalogue title when categories exist', () => {
    renderWithMockStore(<Homepage />);
    expect(screen.getByText('Catalogue')).toBeInTheDocument();
  });

  test('renders category cards with images and titles', () => {
    renderWithMockStore(<Homepage />);
    mockCategories.forEach(cat => {
      expect(screen.getByText(cat.name)).toBeInTheDocument();
    });
    const images = screen.getAllByRole('img');
    expect(images[0]).toHaveAttribute('src', mockCategories[0].image);
    expect(images[1]).toHaveAttribute('src', imagePlaceholderUrl);
  });

  test('navigates to category on card click', () => {
    renderWithMockStore(<Homepage />);
    const firstCard = screen.getByText('Alpha').closest('div');
    expect(firstCard).not.toBeNull();
    if (firstCard) {
      fireEvent.click(firstCard);
      expect(mockNavigate).toHaveBeenCalledWith('/categories/1');
    }
  });

  test('shows empty state when no categories', () => {
    (ReactRouter.useOutletContext as jest.Mock).mockReturnValue({
      categories: [],
    });

    renderWithMockStore(<Homepage />);
    expect(
      screen.getByText('There is nothing here yet...')
    ).toBeInTheDocument();
  });
});
