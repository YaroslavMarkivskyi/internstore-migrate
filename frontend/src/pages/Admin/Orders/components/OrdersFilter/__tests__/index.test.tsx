import { fireEvent, render, screen } from '@testing-library/react';
import dayjs from 'dayjs';

import OrdersFilters from '../';
import { ReactNode } from 'react';

const mockSetFilters = jest.fn();
const mockDeleteFilter = jest.fn();

jest.mock('quill', () => {
  return jest.fn().mockImplementation(() => ({
    on: jest.fn(),
    getContents: jest.fn(),
    setContents: jest.fn(),
    root: { innerHTML: '' },
    clipboard: { convert: jest.fn() },
    setText: jest.fn(),
    getText: jest.fn(),
  }));
});

jest.mock('@components/UI/common/SimplePopover', () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

jest.mock('@components/UI/common/DatePicker', () => ({
  __esModule: true,
  default: ({
    onChange,
  }: {
    onChange: (range: { from: any; to: any }) => void;
  }) => (
    <button
      data-testid="mock-datepicker"
      onClick={() =>
        onChange({
          from: dayjs('2024-06-01'),
          to: dayjs('2024-06-10'),
        })
      }
    >
      Mock DatePicker
    </button>
  ),
}));

const setup = (propsOverride = {}) => {
  render(
    <OrdersFilters
      setFilters={mockSetFilters}
      deleteFilter={mockDeleteFilter}
      status={['new', 'pending']}
      archived={true}
      date={[{ from: dayjs('2024-01-01'), to: dayjs('2024-01-05') }]}
      {...propsOverride}
    />
  );
};

describe('OrdersFilters Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders status filter tags', () => {
    setup();
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  test('renders date filter tag', () => {
    setup();
    expect(screen.getByText('01/01/2024 - 01/05/2024')).toBeInTheDocument();
  });

  test('removes a status tag when clicking remove', () => {
    setup();
    const removeButton = screen.getByLabelText('Remove New');
    fireEvent.click(removeButton);
    expect(mockSetFilters).toHaveBeenCalledWith({ status: ['pending'] });
  });

  test('removes last status tag and deletes filter', () => {
    setup({ status: ['new'] });
    const removeButton = screen.getByLabelText('Remove New');
    fireEvent.click(removeButton);
    expect(mockDeleteFilter).toHaveBeenCalledWith('status');
  });

  test('removes a date range when clicking remove', () => {
    setup();
    const removeButton = screen.getByLabelText(
      'Remove 01/01/2024 - 01/05/2024'
    );
    fireEvent.click(removeButton);
    expect(mockDeleteFilter).toHaveBeenCalledWith('date');
  });

  test('toggles archived switch', () => {
    setup();
    const switchInput = screen.getByRole('checkbox');
    fireEvent.click(switchInput);
    expect(mockSetFilters).toHaveBeenCalledWith({ archived: false });
  });

  test('adds a new date range when DatePicker is used', () => {
    setup({ date: [] });

    const dateButton = screen.getByTestId('mock-datepicker');
    fireEvent.click(dateButton);

    expect(mockSetFilters).toHaveBeenCalledWith({
      date: [
        {
          from: dayjs('2024-06-01'),
          to: dayjs('2024-06-10'),
        },
      ],
    });
  });
});
