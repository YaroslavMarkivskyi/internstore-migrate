import { Box, styled } from '@mui/material';

import colors from '@constants/colors';

export const CheckoutWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  width: '100%',
});

export const CheckoutContent = styled(Box)({
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'flex-start',
  padding: '25px',
  marginBottom: '50px',
  background: 'white',
  boxShadow: `0px 4px 15px ${colors.border}`,
  borderRadius: '5px',
  width: '100%',
  gap: '25px',
});
