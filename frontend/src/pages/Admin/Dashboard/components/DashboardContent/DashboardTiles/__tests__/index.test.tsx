import { render, screen } from '@testing-library/react';
import DashboardTiles from '../index';
import { statsData } from '../mockData';

// Mock the child components
jest.mock('../components/StatCard', () => {
  return {
    __esModule: true,
    default: ({ title, value }: { title: string; value: any }) => (
      <div data-testid={`stat-card-${title}`}>
        {title}: {value}
      </div>
    ),
  };
});

jest.mock('../components/TempCard', () => {
  return {
    __esModule: true,
    default: ({ store, temp }: { store: string; temp: number }) => (
      <div data-testid={`temp-card-${store}`}>
        {store}: {temp}°C
      </div>
    ),
  };
});

describe('DashboardTiles Component', () => {
  test('renders all stat cards with correct data', () => {
    render(<DashboardTiles />);

    // Check if stat cards are rendered with correct data
    const salesCard = screen.getByTestId('stat-card-Sales this week');
    expect(salesCard).toBeInTheDocument();
    expect(salesCard).toHaveTextContent(
      `Sales this week: ${statsData.salesThisWeek}`
    );

    const newOrdersCard = screen.getByTestId('stat-card-New orders');
    expect(newOrdersCard).toBeInTheDocument();
    expect(newOrdersCard).toHaveTextContent(
      `New orders: ${statsData.newOrders}`
    );

    const pendingPaymentCard = screen.getByTestId('stat-card-Pending payment');
    expect(pendingPaymentCard).toBeInTheDocument();
    expect(pendingPaymentCard).toHaveTextContent(
      `Pending payment: ${statsData.pendingPayment}`
    );

    const valueThisWeekCard = screen.getByTestId('stat-card-Value this week');
    expect(valueThisWeekCard).toBeInTheDocument();
    expect(valueThisWeekCard).toHaveTextContent(
      `Value this week: ${statsData.valueThisWeek}`
    );
  });

  test('renders temperature cards for all stores', () => {
    render(<DashboardTiles />);

    // Check if temperature cards are rendered for each store
    statsData.temperatures.forEach(temp => {
      const tempCard = screen.getByTestId(`temp-card-${temp.store}`);
      expect(tempCard).toBeInTheDocument();
      expect(tempCard).toHaveTextContent(`${temp.store}: ${temp.temp}°C`);
    });
  });
});
