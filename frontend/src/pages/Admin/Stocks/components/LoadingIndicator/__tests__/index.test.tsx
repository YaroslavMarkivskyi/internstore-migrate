import { render, screen } from '@testing-library/react';
import { LoadingIndicator } from '../';

describe('LoadingIndicator', () => {
  it('should render CircularProgress component', () => {
    render(<LoadingIndicator />);

    const circularProgressElement = screen.getByRole('progressbar');

    expect(circularProgressElement).toBeInTheDocument();
  });

  it('should have correct styling', () => {
    render(<LoadingIndicator />);

    const circularProgressElement = screen.getByRole('progressbar');

    expect(circularProgressElement.parentElement).toHaveStyle('display: flex');
    expect(circularProgressElement.parentElement).toHaveStyle(
      'justify-content: center'
    );
  });
});
