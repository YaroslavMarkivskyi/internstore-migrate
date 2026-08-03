import { Box, styled } from '@mui/material';

import colors from '@constants/colors';

export const MenuWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  rowGap: '20px',
  marginTop: '40px',
});

export const MenuContent = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  alignItems: 'flex-start',
  padding: '20px',
  width: '180px',
  gap: '20px',
  background: 'white',
  boxShadow: ` 0px 4px 15px ${colors.border}`,
  borderRadius: '5px',
  '& a': {
    fontFamily: 'Noto Sans',
    fontWeight: 400,
    fontSize: '16px',
    cursor: 'pointer',
    '&.active': {
      color: colors.secondary.accent100,
      fontWeight: 600,
    },
  },
});

export const ContentWrapper = styled(Box)({
  flexGrow: 1,
  display: 'flex',
  justifyContent: 'flex-start',
  marginTop: '40px',
  paddingLeft: '60px',
  width: '100%',
  overflowX: 'hidden',
});
