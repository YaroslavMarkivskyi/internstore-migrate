import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const OrdersContainer = styled(Box)(() => ({
  paddingTop: '40px',
  paddingBottom: '32px',
  paddingLeft: 0,
  paddingRight: 0,
  fontFamily: '"Noto Sans", sans-serif',
  margin: 0,
  width: '100%',
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
}));

export const OrdersHeader = styled(Typography)(() => ({
  fontWeight: 500,
  fontSize: '24px',
  lineHeight: '100%',
  letterSpacing: '0%',
  color: colors.dashboard,
  marginBottom: '24px',
  padding: 0,
}));
