import React, {
  cloneElement,
  FC,
  isValidElement,
  ReactNode,
  SyntheticEvent,
  useState,
} from 'react';

import { ButtonProps, MenuItem, MenuProps } from '@mui/material';

import CustomMenuItem, { CustomMenuOption } from '../../admin/CustomMenuItem';

import { MenuBase, TriggerWrapper } from './styles';

type MenuOnClick = (e: SyntheticEvent) => void;

export interface MenuItem extends CustomMenuOption {
  /** Text to be displayed in the option */
  label: string;
  /** Function to be called when this option is clicked */
  onClick: MenuOnClick;
  disabled?: boolean;
}

export interface MenuPopupProps extends Omit<MenuProps, 'open' | 'anchorEl'> {
  /** Element that will trigger the Menu to open */
  children: ReactNode;
  /** Function to be called when menu is closed */
  onClose?: () => void;
  /** Options to be rendered inside the Menu */
  options: MenuItem[];
}

const MenuPopup: FC<MenuPopupProps> = ({
  children,
  onClose,
  options,
  ...menuProps
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleTriggerClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    onClose?.();
  };

  const handleOptionClick = (cb: MenuOnClick) => {
    return (e: SyntheticEvent) => {
      handleMenuClose();
      cb(e);
    };
  };

  return (
    <>
      <TriggerWrapper onClick={handleTriggerClick}>
        {isValidElement<ButtonProps>(children) &&
          cloneElement(children, {
            variant: open ? 'contained' : 'outlined',
            ...children.props,
          })}
      </TriggerWrapper>
      <MenuBase
        anchorEl={anchorEl}
        open={open}
        onClose={handleMenuClose}
        {...menuProps}
      >
        {options.map(option => (
          <CustomMenuItem
            key={option.label}
            startComponent={option?.startComponent}
            endComponent={option?.endComponent}
            onClick={handleOptionClick(option.onClick)}
            disabled={option.disabled}
          >
            {option.label}
          </CustomMenuItem>
        ))}
      </MenuBase>
    </>
  );
};

export default MenuPopup;
