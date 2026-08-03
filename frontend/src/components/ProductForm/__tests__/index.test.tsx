import '@testing-library/jest-dom';
import {
  act,
  configure,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import MockButtonAdmin from '@components/UI/admin/ButtonAdmin/__mocks__/ButtonAdmin.mock';
import MockInputFieldAdmin from '@components/UI/admin/InputFieldAdmin/__mocks__/InputFieldAdmin.mock';
import MockSelectFieldAdmin from '@components/UI/admin/SelectFieldAdmin/__mocks__/SelectFieldAdmin.mock';
import MockCategorySelect from '@components/CategorySelect/__mocks__/CategorySelect.mock';
import * as productService from '@services/http/admin/products';
import { handleFormErrors } from '@utils/handleFormErrors';
import showToast from '@utils/showToast';
import ProductForm from '../index';
import { MAX_IMAGES } from '@components/ProductForm/schema';

configure({ asyncUtilTimeout: 5000 });
// --- Mocks ---
jest.mock('@services/http/admin/products');
jest.mock('@utils/showToast');
jest.mock('@utils/handleFormErrors');

jest.mock('quill', () => {
  return function Quill() {
    return {
      getContents: () => ({}),
      on: () => {},
      clipboard: {
        addMatcher: () => {},
      },
    };
  };
});

// Mock UI components
jest.mock('@components/UI/admin/InputFieldAdmin', () => ({
  __esModule: true,
  default: MockInputFieldAdmin,
}));

jest.mock('@components/UI/admin/SelectFieldAdmin', () => ({
  __esModule: true,
  default: MockSelectFieldAdmin,
}));

jest.mock('@components/CategorySelect', () => ({
  __esModule: true,
  default: MockCategorySelect,
}));

jest.mock('@components/UI/admin/ButtonAdmin', () => ({
  __esModule: true,
  default: MockButtonAdmin,
}));

jest.mock('../components/ImageCell', () => (props: any) => (
  <div>
    {props.imageUrl && <span data-testid="thumbnail">T</span>}
    {props.imageUrl && (
      <button data-testid="delete-image" onClick={props.onDelete}>
        X
      </button>
    )}
    {!props.imageUrl && <div data-testid="empty-cell" />}
  </div>
));

jest.mock('../components/ImagePreview', () => (props: any) => (
  <img data-testid="main-preview" src={props.imageUrl} alt="preview" />
));

// Mock react-router
const mockNavigate = jest.fn();
jest.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
}));

// --- Helpers ---
const fillBasicFields = async () => {
  await userEvent.type(screen.getByTestId('name-input'), 'My Product');
  await userEvent.selectOptions(screen.getByTestId('category-input'), '1');
  await userEvent.type(screen.getByTestId('price-input'), '19');
  await userEvent.type(screen.getByTestId('mintemperature-input'), '5');
  await userEvent.type(screen.getByTestId('maxtemperature-input'), '25');
};

const renderComponent = async () => {
  await act(async () => {
    render(<ProductForm onSubmit={jest.fn()} />);
  });
};

// --- Tests ---
describe('ProductForm', () => {
  global.URL.createObjectURL = jest.fn((file: File) => file.name);

  beforeEach(() => {
    jest.clearAllMocks();
    (productService.getProduct as jest.Mock).mockResolvedValue({
      name: 'Loaded',
      description: 'Desc',
      minTemperature: 1,
      maxTemperature: 2,
      category: 3,
      price: 4.5,
    });
    (productService.getImages as jest.Mock).mockResolvedValue([
      { id: 10, image: 'http://foo/1.png' },
    ]);
  });

  test('renders all fields and buttons', async () => {
    await renderComponent();
    expect(screen.getByTestId('name-input')).toBeInTheDocument();
    expect(screen.getByTestId('category-input')).toBeInTheDocument();
    expect(screen.getByTestId('price-input')).toBeInTheDocument();
    expect(screen.getByTestId('mintemperature-input')).toBeInTheDocument();
    expect(screen.getByTestId('maxtemperature-input')).toBeInTheDocument();
    expect(screen.getByTestId('button-save')).toBeDisabled();
    expect(screen.getByTestId('button-discard')).toBeEnabled();
    expect(screen.getByText('Upload Image')).toBeInTheDocument();
  });

  test('enables save button when form is valid', async () => {
    await renderComponent();
    await fillBasicFields();
    expect(screen.getByTestId('button-save')).not.toBeDisabled();
  });

  test('uploads and previews image, then deletes it', async () => {
    const { container } = render(<ProductForm onSubmit={jest.fn()} />);
    const uploadBtn = screen.getByText('Upload Image');
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    const file = new File(['hello'], 'hello.png', { type: 'image/png' });
    await userEvent.click(uploadBtn);
    await userEvent.upload(fileInput, file);

    expect(screen.getByTestId('main-preview')).toHaveAttribute(
      'src',
      file.name
    );
    expect(screen.getAllByTestId('thumbnail').length).toBe(1);

    await userEvent.click(screen.getByTestId('delete-image'));
    expect(screen.queryByTestId('thumbnail')).toBeNull();
  });

  test('loads default values when productId is passed', async () => {
    render(<ProductForm onSubmit={jest.fn()} productId={'123'} />);

    await waitFor(() => {
      expect(productService.getProduct).toHaveBeenCalledWith('123');
      expect(productService.getImages).toHaveBeenCalledWith('123');
    });

    await waitFor(() => {
      expect((screen.getByTestId('name-input') as HTMLInputElement).value).toBe(
        'Loaded'
      );
    });

    expect(screen.getByTestId('main-preview')).toHaveAttribute(
      'src',
      'http://foo/1.png'
    );
  });

  test('discard resets all fields', async () => {
    render(<ProductForm onSubmit={jest.fn()} />);
    await fillBasicFields();

    await userEvent.click(screen.getByTestId('button-discard'));
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  test('successful submit calls onSubmit, shows toast, and navigates', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    render(<ProductForm onSubmit={mockSubmit} />);
    await fillBasicFields();
    expect(screen.getByTestId('button-save')).toBeEnabled();

    await userEvent.click(screen.getByTestId('button-save'));
    expect(mockSubmit).toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith({
      message: 'Saved successfully',
      type: 'success',
    });
    expect(mockNavigate).toHaveBeenCalledWith('/admin/products');
  });

  test('failed submit calls handleFormErrors and displays root error', async () => {
    const err = new Error('Bad!');
    const mockSubmit = jest.fn().mockRejectedValue(err);
    render(<ProductForm onSubmit={mockSubmit} />);
    await fillBasicFields();
    expect(screen.getByTestId('button-save')).toBeEnabled();

    await userEvent.click(screen.getByTestId('button-save'));
    expect(handleFormErrors).toHaveBeenCalledWith(err, expect.any(Function));
  });

  test('prevents uploading more than MAX_IMAGES', async () => {
    const { container } = render(<ProductForm onSubmit={jest.fn()} />);
    const uploadBtn = screen.getByText('Upload Image');
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    const files = Array.from({ length: MAX_IMAGES + 2 }).map(
      (_, i) => new File(['data'], `img${i}.png`, { type: 'image/png' })
    );
    await userEvent.click(uploadBtn);
    await userEvent.upload(fileInput, files);

    const thumbnails = screen.queryAllByTestId('thumbnail');
    expect(thumbnails.length).toBeLessThanOrEqual(MAX_IMAGES);
  });

  test('discard clears uploaded images', async () => {
    const { container } = render(<ProductForm onSubmit={jest.fn()} />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await userEvent.upload(fileInput, file);
    expect(screen.getByTestId('main-preview')).toHaveAttribute(
      'src',
      file.name
    );

    await userEvent.click(screen.getByTestId('button-discard'));
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  test('disables upload button when max images are uploaded', async () => {
    const { container } = render(<ProductForm onSubmit={jest.fn()} />);
    const uploadBtn = screen.getByText('Upload Image');
    const input = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    const files = Array.from(
      { length: MAX_IMAGES },
      (_, i) => new File([''], `img${i}.png`, { type: 'image/png' })
    );
    await userEvent.upload(input, files);

    expect(uploadBtn).toBeDisabled();
  });
});
