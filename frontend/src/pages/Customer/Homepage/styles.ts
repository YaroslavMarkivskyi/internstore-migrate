import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const HomepageWrapper = styled(Box)({
  flexGrow: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-start',
  rowGap: '20px',
  maxWidth: '100%',
});

export const NothingText = styled(Typography)({
  color: colors.placeholder,
  fontSize: '14px',
});

export const CategoriesContainer = styled(Box)({
  display: 'flex',
  flexWrap: 'wrap',
  gap: '40px',
});

export const CategoryCard = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  padding: '20px',
  gap: '24px',
  width: '150px',
  background: 'white',
  boxShadow: `0px 4px 15px ${colors.border}`,
  borderRadius: '5px',
  cursor: 'pointer',
});

export const CategoryImage = styled('img')({
  width: '100px',
  height: '100px',
  objectFit: 'contain',
});

export const CategoryTitle = styled(Typography)({
  fontWeight: 600,
  fontSize: '16px',
});
