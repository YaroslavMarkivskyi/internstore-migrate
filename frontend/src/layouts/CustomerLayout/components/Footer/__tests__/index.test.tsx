import { screen } from '@testing-library/react';
import Footer from '../index';
import { renderWithRouter } from '@utils/testRenderWithRouter';

jest.mock('@components/UI/common/Logo', () => () => (
  <div data-testid="logo">Logo</div>
));

const mockNavigate = jest.fn();

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  useNavigate: () => mockNavigate,
}));

describe('Footer component', () => {
  it('renders Logo, current date, and Connect With Us link', () => {
    renderWithRouter(<Footer />);

    expect(screen.getByTestId('logo')).toBeInTheDocument();

    const today = new Date().toLocaleDateString('en-GB');
    expect(screen.getByText(today)).toBeInTheDocument();

    const mailtoLink = screen.getByRole('link');
    expect(mailtoLink).toHaveAttribute('href');
    expect(mailtoLink.getAttribute('href')).toMatch(/^mailto:/i);
  });
});
