import { Box, styled, Typography } from '@mui/material';

import colors from '../../../../constants/colors';

export const LogoContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  paddingLeft: 16,
  paddingRight: 16,
  cursor: 'pointer',
});

export const LogoImage = styled('img')({
  width: 36,
  height: 36,
});

export const LogoTextContainer = styled(Box)({
  marginLeft: 12,
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'center',
  flexDirection: 'column',
});

export const BrandName = styled(Typography)({
  fontWeight: 'bold',
  color: colors.secondary.accent100,
});
