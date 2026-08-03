import { Box, Radio, styled } from '@mui/material';

import colors from '@constants/colors';

export const CustomRadio = styled(Radio)({
  '&.Mui-checked': {
    color: colors.primary.accent100,
  },
});

export const FormHeader = styled(Box)({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 16,
});
