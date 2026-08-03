import { Box, styled } from '@mui/material';

export const IconWrapper = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  marginRight: theme.spacing(1),
}));

export const MenuIcon = styled('img')({
  width: '18px',
  height: '18px',
  display: 'block',
});

export const IconButtonStyle = {
  padding: '4px',
  borderRadius: '4px',
  width: '28px',
  height: '28px',
  minWidth: '28px',
  minHeight: '28px',
};
