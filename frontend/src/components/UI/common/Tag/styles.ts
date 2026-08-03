import { Box, styled } from '@mui/material';

import colors from '../../../../constants/colors';

export const Container = styled(Box)({
  display: 'flex',
  flexDirection: 'row',
  justifyContent: 'center',
  alignItems: 'center',
  padding: ' 5px 8px',
  gap: '8px',
  background: colors.backgroundDisabled,
  borderRadius: '10px',
});

export const IconWrapper = styled(Box)({
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  '& .MuiSvgIcon-root': {
    fill: colors.placeholder,
  },
});
