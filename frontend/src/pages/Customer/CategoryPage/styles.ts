import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const PageContent = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-start',
  alignItems: 'center',
});

export const Title = styled(Typography)({
  alignSelf: 'flex-start',
});

export const Subtitle = styled(Typography)({
  margin: '80px 0 auto',
  fontSize: '20px',
  color: colors.text600,
});

export const ProductsContainer = styled(Box)({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
  gap: '15px',
  width: '100%',
  margin: '20px 0',
  justifyItems: 'center',
});
