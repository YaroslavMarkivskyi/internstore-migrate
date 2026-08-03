import { cloneElement, FC, isValidElement, ReactNode } from 'react';

import { useLocation, useNavigate } from 'react-router';

import { ListItemText } from '@mui/material';

import { MenuItemButton, MenuItemIconWrapper, MenuListItem } from './styles';

export interface NavbarTabProps {
  /** Text to display */
  text: string;
  /** Icon to display next to text */
  icon: ReactNode;
  /** path of tab */
  path: string;
  /** Optional function to invoke when clicked on tab */
  onClick?: (path: string) => void;
}

/** Component representing Navbar Tab on side panel on Admin page */
const NavbarTab: FC<NavbarTabProps> = ({ text, icon, path, onClick }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const currentPath = location.pathname;

  const handleClick = (path: string) => {
    navigate(path);
    onClick?.(path);
  };

  const isActive = currentPath === path || currentPath.startsWith(path + '/');

  return (
    <MenuListItem key={text} disablePadding>
      <MenuItemButton selected={isActive} onClick={() => handleClick(path)}>
        <MenuItemIconWrapper selected={isActive}>
          {isValidElement<HTMLImageElement>(icon) &&
            cloneElement(icon, { width: 18, height: 18 })}
        </MenuItemIconWrapper>
        <ListItemText primary={text} />
      </MenuItemButton>
    </MenuListItem>
  );
};

export default NavbarTab;
