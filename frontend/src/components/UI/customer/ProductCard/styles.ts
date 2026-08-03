import ShoppingCartOutlinedIcon from '@mui/icons-material/ShoppingCartOutlined';
import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const CardWrapper = styled(Box)({
  padding: '20px',
  width: '200px',
  height: '240px',
  background: 'white',
  boxShadow: `0px 4px 15px ${colors.border}`,
  borderRadius: '5px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'flex-start',
  cursor: 'pointer',
  transition: 'box-shadow 0.2s ease-in',
  '&:hover': {
    boxShadow: `0px 8px 25px ${colors.border}`,
  },
});

export const CardImage = styled('img')({
  height: '100px',
  width: '100px',
  objectFit: 'contain',
});

export const CardTitle = styled(Typography)({
  fontSize: '14px',
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  width: '100%',
  marginTop: '25px',
});

export const CardTitleContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  width: '100%',
  marginTop: 'auto',
});

export const CardPrice = styled(Typography)({
  fontWeight: 600,
  fontSize: '16px',
});

export const CartSecondaryText = styled(Typography)({
  fontSize: '16px',
  color: colors.textDisabled100,
});

export const CartIcon = styled(ShoppingCartOutlinedIcon)({
  fontSize: '20px',
});
