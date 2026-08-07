import { render, screen, fireEvent } from '@testing-library/react';
import { createMemoryHistory } from 'history';
import { Router } from 'react-router-dom';
import { StockTabs } from '..';
import { IStock } from 'src/types/stocks/interfaces';

describe('StockTabs', () => {
  const mockStocks: IStock[] = [
    { id: '1', name: 'Apple' },
    { id: '2', name: 'Tesla' },
  ];

  const setup = (selectedStock = '1') => {
    const onEditClick = jest.fn();
    const history = createMemoryHistory({
      initialEntries: ['/admin/stocks/1'],
    });

    const utils = render(
      <Router location={history.location} navigator={history}>
        <StockTabs
          stocks={mockStocks}
          selectedStock={selectedStock}
          onEditClick={onEditClick}
        />
      </Router>
    );

    return { onEditClick, history, ...utils };
  };

  it('renders all stock tabs including "All Stocks"', () => {
    setup();

    expect(screen.getByText('All Stocks')).toBeInTheDocument();
    expect(screen.getByText('Apple')).toBeInTheDocument();
    expect(screen.getByText('Tesla')).toBeInTheDocument();
  });

  it('clicking on a tab navigates correctly', () => {
    const { history } = setup();

    fireEvent.click(screen.getByText('Tesla'));

    expect(history.location.pathname).toBe('/admin/stocks/2');
  });

  it('clicking on edit icon calls onEditClick and prevents navigation', () => {
    const { onEditClick, history } = setup('2');

    fireEvent.click(screen.getByLabelText('Edit stock'));

    expect(onEditClick).toHaveBeenCalledWith({ id: '2', name: 'Tesla' });
    expect(history.location.pathname).toBe('/admin/stocks/1'); // no nav occurred
  });

  it('only renders an edit icon for the selected tab', () => {
    setup('1');

    // Apple (id "1") is selected -- exactly one edit icon, and it's Apple's.
    const editIcons = screen.getAllByLabelText('Edit stock');
    expect(editIcons).toHaveLength(1);
  });
});
