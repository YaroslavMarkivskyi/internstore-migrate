import { ListItem, ListItemButton, ListItemIcon, styled } from '@mui/material';

import colors from '../../../../constants/colors';

export const MenuListItem = styled(ListItem)({
  padding: 0,
});

interface MenuItemButtonProps {
  selected: boolean;
}

export const MenuItemButton = styled(ListItemButton, {
  shouldForwardProp: prop => prop !== 'selected',
})<MenuItemButtonProps>(({ selected }) => ({
  borderRadius: '8px',
  backgroundColor: selected ? colors.secondary.accent100 : 'transparent',
  color: selected ? '#FFFFFF' : 'inherit',
  '&.Mui-selected': {
    backgroundColor: colors.secondary.accent100,
    '&:hover': {
      backgroundColor: colors.secondary.accent200,
    },
  },
  '&:hover': {
    backgroundColor: selected
      ? colors.secondary.accent200
      : colors.secondary.accent1000,
  },
}));

interface MenuItemIconProps {
  selected: boolean;
}

export const MenuItemIconWrapper = styled(ListItemIcon, {
  shouldForwardProp: prop => prop !== 'selected',
})<MenuItemIconProps>(({ selected }) => ({
  color: selected ? '#FFFFFF' : 'inherit',
  minWidth: 40,
  '& img': {
    filter: selected ? 'brightness(0) invert(1)' : 'none',
  },
}));
