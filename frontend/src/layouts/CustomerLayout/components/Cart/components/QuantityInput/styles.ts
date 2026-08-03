import { Box, IconButton, styled } from '@mui/material';

import InputFieldCustomer from '@components/UI/customer/InputFieldCustomer';

export const Wrapper = styled(Box)({
  display: 'flex',
  gap: '11px',
  alignItems: 'center',
});

export const QuantityInputBase = styled(InputFieldCustomer)({
  '& .MuiOutlinedInput-root': {
    width: '48px',
    height: '48px',
    background: 'transparent',
    '& .MuiOutlinedInput-input': {
      padding: '2px',
      textAlign: 'center',
    },
  },
});

export const ControlsButton = styled(IconButton)({
  padding: '4px',
});
