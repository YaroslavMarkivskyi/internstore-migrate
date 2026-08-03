import { Box, styled } from '@mui/material';

export const OrderStatusIndicator = styled(Box)({
  width: '8px',
  height: '8px',
  borderRadius: '100%',
});

export const Wrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  columnGap: '10px',
});
