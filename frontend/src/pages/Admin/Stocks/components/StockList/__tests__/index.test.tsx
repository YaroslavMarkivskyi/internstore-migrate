import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import StocksList from '../';
import { useModal } from '../../../hooks/ModalStockContext';
import * as validateUtils from '../utils/validateSelectedStock';

// Mock useModal
jest.mock('../../../hooks/ModalStockContext', () => ({
  useModal: jest.fn(),
}));

// Mock components
jest.mock('../components/StockTabs', () => ({
  StockTabs: ({ selectedStock }: any) => (
    <div data-testid="stock-tabs">StockTabs - ID: {selectedStock}</div>
  ),
}));

jest.mock('../../LoadingIndicator', () => ({
  LoadingIndicator: jest.fn(() => (
    <div data-testid="loading-indicator">Loading...</div>
  )),
}));

jest.mock('.././components/InvalidStockMessage', () => ({
  InvalidStockMessage: jest.fn(() => (
    <div data-testid="invalid-stock-message">Invalid Stock</div>
  )),
}));

describe('StocksList', () => {
  const mockOpenModal = jest.fn();

  beforeEach(() => {
    (useModal as jest.Mock).mockReturnValue({ openModal: mockOpenModal });
  });

  const renderComponent = (stockId: string, props: any) => {
    return render(
      <MemoryRouter initialEntries={[`/stocks/${stockId}`]}>
        <Routes>
          <Route path="/stocks/:stockId" element={<StocksList {...props} />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders loading state', () => {
    renderComponent('1', { stocks: [], loading: true });

    expect(screen.getByTestId('loading-indicator')).toBeInTheDocument();
  });

  it('renders invalid stock message if stockId is not valid', () => {
    jest.spyOn(validateUtils, 'isValidStockId').mockReturnValue(false);

    renderComponent('999', {
      stocks: [{ id: '1', name: 'Stock A' }],
      loading: false,
    });

    expect(screen.getByTestId('invalid-stock-message')).toBeInTheDocument();
  });

  it('renders stock tabs if stockId is valid', () => {
    jest.spyOn(validateUtils, 'isValidStockId').mockReturnValue(true);

    renderComponent('1', {
      stocks: [{ id: '1', name: 'Stock A' }],
      loading: false,
    });

    expect(screen.getByTestId('stock-tabs')).toBeInTheDocument();
    expect(screen.getByText(/ID: 1/)).toBeInTheDocument();
  });
});
