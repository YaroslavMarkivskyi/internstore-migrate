import { render, waitFor } from '@testing-library/react';
import { stockService } from '@services/http';
import showToast from '@utils/showToast';
import { useStocks } from '../useStocks';

jest.mock('@services/http', () => ({
  stockService: {
    getAllStocks: jest.fn(),
  },
}));

jest.mock('@utils/showToast');

const TestComponent = () => {
  const { stocks, loading } = useStocks();
  return (
    <div>
      {loading ? 'Loading...' : 'Loaded'}
      <div data-testid="stocks">{JSON.stringify(stocks)}</div>
    </div>
  );
};

describe('useStocks', () => {
  it('should fetch stocks and set loading to false', async () => {
    const mockStocks = [{ id: 1, name: 'Apple' }];
    (stockService.getAllStocks as jest.Mock).mockResolvedValue(mockStocks);

    const { getByText, getByTestId } = render(<TestComponent />);

    expect(getByText('Loading...')).toBeInTheDocument();

    await waitFor(() => expect(getByText('Loaded')).toBeInTheDocument());

    expect(getByTestId('stocks').textContent).toBe(JSON.stringify(mockStocks));
  });

  it('should show error toast if the fetch fails', async () => {
    (stockService.getAllStocks as jest.Mock).mockRejectedValue(
      new Error('Failed to fetch')
    );

    const { getByText } = render(<TestComponent />);

    expect(getByText('Loading...')).toBeInTheDocument();

    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith({
        message: 'Failed to fetch stocks.',
        type: 'error',
      })
    );
    expect(getByText('Loaded')).toBeInTheDocument();
  });
});
