import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const CategoriesWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  rowGap: '20px',
  marginTop: '40px',
});

export const CategoriesContent = styled(Box)({
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
});

export const CategoryLink = styled(Typography)({
  cursor: 'pointer',
  '&.active': {
    color: colors.secondary.accent100,
    fontWeight: 600,
  },
});

export const ContentWrapper = styled(Box)({
  flexGrow: 1,
  display: 'flex',
  justifyContent: 'center',
  marginTop: '40px',
  paddingLeft: '60px',
});
