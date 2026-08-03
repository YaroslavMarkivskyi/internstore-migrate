import { useCallback, useMemo } from 'react';

import { useNavigate } from 'react-router';

import { SecurityOutlined, ShoppingCartOutlined } from '@mui/icons-material';

import NavbarTab from '@components/UI/admin/NavbarTab';
import Logo from '@components/UI/common/Logo';
import CategoriesIcon from '@components/UI/icons/CategoriesIcon';
import DashboardIcon from '@components/UI/icons/DashboardIcon';
import OrdersIcon from '@components/UI/icons/OrdersIcon';
import ProductsIcon from '@components/UI/icons/ProductsIcon';
import StocksIcon from '@components/UI/icons/StocksIcon';

import { MenuDivider, MenuIcon, MenuList, SidebarContainer } from './styles';

const AdminSidebar = () => {
  const navigate = useNavigate();

  const menuItems = useMemo(
    () => [
      {
        text: 'Dashboard',
        icon: (
          <MenuIcon>
            <DashboardIcon />
          </MenuIcon>
        ),
        path: '/admin/dashboard',
      },
      {
        text: 'Products',
        icon: (
          <MenuIcon>
            <ProductsIcon />
          </MenuIcon>
        ),
        path: '/admin/products',
      },
      {
        text: 'Categories',
        icon: (
          <MenuIcon>
            <CategoriesIcon />
          </MenuIcon>
        ),
        path: '/admin/categories',
      },
      {
        text: 'Stocks',
        icon: (
          <MenuIcon>
            <StocksIcon />
          </MenuIcon>
        ),
        path: '/admin/stocks',
      },
      {
        text: 'Orders',
        icon: (
          <MenuIcon>
            <OrdersIcon />
          </MenuIcon>
        ),
        path: '/admin/orders',
      },
    ],
    []
  );

  const bottomMenuItems = useMemo(
    () => [
      { text: 'Security', icon: <SecurityOutlined />, path: '/admin/security' },
      { text: 'Go to online shop', icon: <ShoppingCartOutlined />, path: '/' },
    ],
    []
  );

  const handleClick = useCallback(
    (path: string) => {
      navigate(path);
    },
    [navigate]
  );

  return (
    <SidebarContainer elevation={0}>
      <Logo onClick={() => navigate('/admin/dashboard')} isAdmin={true} />
      <MenuList>
        {menuItems.map(item => (
          <NavbarTab
            key={item.text}
            text={item.text}
            icon={item.icon}
            path={item.path}
            onClick={handleClick}
          />
        ))}
        <MenuDivider />
        {bottomMenuItems.map(item => (
          <NavbarTab
            key={item.text}
            text={item.text}
            icon={item.icon}
            path={item.path}
            onClick={handleClick}
          />
        ))}
      </MenuList>
    </SidebarContainer>
  );
};

export default AdminSidebar;
