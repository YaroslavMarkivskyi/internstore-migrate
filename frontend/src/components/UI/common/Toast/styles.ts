import { Box, styled } from '@mui/material';

import colors from '@constants/colors';

export const ToastContainer = styled(Box)({
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  columnGap: '12px',
  color: colors.text100,
  padding: '15px 36px',
  borderRadius: '10px',
  boxShadow: `0px 4px 15px ${colors.border}`,
  '& .MuiSvgIcon-root': {
    fontSize: '24px',
  },
  '& .MuiTypography-root': {
    whiteSpace: 'nowrap',
    wordBreak: 'keep-all',
  },
});
