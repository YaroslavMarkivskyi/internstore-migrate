import { MemoryRouter } from 'react-router';

import categoriesIcon from '../../icons/CategoriesIcon/icon.svg';
import dashboardIcon from '../../icons/DashboardIcon/icon.svg';
import ordersIcon from '../../icons/OrdersIcon/icon.svg';
import productsIcon from '../../icons/ProductsIcon/icon.svg';
import stocksIcon from '../../icons/StocksIcon/icon.svg';

import NavbarTab from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof NavbarTab> = {
  component: NavbarTab,
  tags: ['autodocs'],
  decorators: [
    Story => (
      <MemoryRouter initialEntries={['/']}>
        <Story />
      </MemoryRouter>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof NavbarTab>;

export const Base: Story = {
  args: {
    text: 'Dashboard',
    path: '/dashboard',
    icon: <img src={dashboardIcon} alt="Dashboard" />,
  },
};

export const Selected: Story = {
  args: {
    text: 'Dashboard',
    path: '/',
    icon: <img src={dashboardIcon} alt="Dashboard" />,
  },
};

const menuItems = [
  {
    text: 'Dashboard',
    icon: <img src={dashboardIcon} alt="Dashboard" />,
    path: '/admin/dashboard',
  },
  {
    text: 'Products',
    icon: <img src={productsIcon} alt="Products" />,
    path: '/admin/products',
  },
  {
    text: 'Categories',
    icon: <img src={categoriesIcon} alt="Categories" />,
    path: '/admin/categories',
  },
  {
    text: 'Stocks',
    icon: <img src={stocksIcon} alt="Stocks" />,
    path: '/admin/stocks',
  },
  {
    text: 'Orders',
    icon: <img src={ordersIcon} alt="Orders" />,
    path: '/admin/orders',
  },
];

export const InMenu: Story = {
  render: () => (
    <div
      style={{
        flex: '1 1 auto',
        paddingLeft: 8,
        paddingRight: 8,
        overflowY: 'auto',
      }}
    >
      {menuItems.map(item => (
        <NavbarTab
          text={item.text}
          icon={item.icon}
          path={item.path}
          key={item.path}
        />
      ))}
    </div>
  ),
};
