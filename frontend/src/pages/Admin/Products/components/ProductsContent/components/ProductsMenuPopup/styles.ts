import { Box, Menu, styled } from '@mui/material';

import colors from '@constants/colors';

export const IconWrapper = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  marginRight: theme.spacing(1),
  '& .MuiSvgIcon-root': {
    color: colors.placeholder,
  },
}));

export const IconButtonStyle = {
  padding: '4px',
  borderRadius: '4px',
  width: '28px',
  height: '28px',
  minWidth: '28px',
  minHeight: '28px',
};

export const MenuBase = styled(Menu)({
  '& .MuiList-root': {
    padding: '8px 0',
    overflowY: 'auto',
    maxHeight: 300,
    minWidth: 200,
  },
  '& .MuiPaper-root': {
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
  },
});

// Container for use with SimplePopover, styled to match MenuBase
export const MenuContainer = styled(Box)({
  padding: '8px 0',
  minWidth: 200,
  maxHeight: 300,
  overflowY: 'auto',
});

export const SelectedMenuItemStyle = {
  backgroundColor: '#F5F3FA',
};
