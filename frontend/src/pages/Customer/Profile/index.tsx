import { Outlet, useLocation, useNavigate } from 'react-router';

import SideMenu from '@components/SideMenu';

interface IRoute {
  label: string;
  path: string;
}

const routes: IRoute[] = [
  { label: 'Orders', path: 'orders' },
  { label: 'Chat history', path: 'chat-history' },
  { label: 'Reviews', path: 'reviews' },
  { label: 'Recently viewed', path: 'recently-viewed' },
];

const Profile = () => {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const handleClick = (path: string) => {
    return () => {
      navigate(`/profile/${path}`);
    };
  };

  const getClassName = (path: string) => {
    return pathname.startsWith(`/profile/${path}`) ? 'active' : '';
  };

  return (
    <SideMenu
      title="My Profile"
      menuContent={routes.map(route => (
        <a
          key={route.path}
          className={getClassName(route.path)}
          onClick={handleClick(route.path)}
        >
          {route.label}
        </a>
      ))}
      content={<Outlet />}
      contentSx={{ pl: '35px' }}
    />
  );
};

export default Profile;
