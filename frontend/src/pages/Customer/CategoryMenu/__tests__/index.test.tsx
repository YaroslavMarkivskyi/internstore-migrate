import { fireEvent, screen, waitFor } from '@testing-library/react';
import CategoryMenu from '../index';
import { getCategoriesPreview } from '@services/http/admin/categories';
import showToast from '@utils/showToast';
import { renderWithRouter } from '@utils/testRenderWithRouter';

jest.mock('@services/http/admin/categories');
jest.mock('@utils/showToast');

const mockNavigate = jest.fn();

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/categories/1' }),
}));

describe('CategoryMenu', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test('shows loader while fetching', async () => {
    (getCategoriesPreview as jest.Mock).mockImplementation(
      () => new Promise(() => {})
    );

    renderWithRouter(<CategoryMenu />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('renders categories when fetched', async () => {
    const categories = [
      { id: 1, name: 'Cat One' },
      { id: 2, name: 'Cat Two' },
    ];
    (getCategoriesPreview as jest.Mock).mockResolvedValue(categories);

    renderWithRouter(<CategoryMenu />);

    for (const cat of categories) {
      await waitFor(() =>
        expect(screen.getByText(cat.name)).toBeInTheDocument()
      );
    }

    const activeLink = screen.getByText('Cat One');
    expect(activeLink).toHaveClass('active');
  });

  test('navigates on category click', async () => {
    const categories = [{ id: 3, name: 'Cat Three' }];
    (getCategoriesPreview as jest.Mock).mockResolvedValue(categories);

    renderWithRouter(<CategoryMenu />);

    const catLink = await screen.findByText('Cat Three');
    fireEvent.click(catLink);

    expect(mockNavigate).toHaveBeenCalledWith('/categories/3');
  });

  test('shows no categories message when empty', async () => {
    (getCategoriesPreview as jest.Mock).mockResolvedValue([]);

    renderWithRouter(<CategoryMenu />);

    await waitFor(() =>
      expect(screen.getByText('No categories yet!')).toBeInTheDocument()
    );
  });

  test('shows error toast on fetch failure', async () => {
    (getCategoriesPreview as jest.Mock).mockRejectedValue(new Error('fail'));

    renderWithRouter(<CategoryMenu />);

    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Error connecting to the server' })
      )
    );
  });
});
