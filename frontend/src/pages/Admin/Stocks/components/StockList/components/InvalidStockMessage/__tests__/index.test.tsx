import { render, screen } from '@testing-library/react';
import { InvalidStockMessage } from '../';

describe('InvalidStockMessage', () => {
  it('renders the correct message', () => {
    render(<InvalidStockMessage />);
    expect(screen.getByText('Invalid stock ID')).toBeInTheDocument();
  });
});
