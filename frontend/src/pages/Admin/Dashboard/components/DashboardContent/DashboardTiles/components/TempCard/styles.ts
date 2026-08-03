import { Box, Card, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

import { cardStyle } from '../../../styles';

export const TempCardContainer = styled(Card)(({ theme }) => ({
  padding: theme.spacing(3),
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  borderRadius: cardStyle.borderRadius,
  boxShadow: cardStyle.boxShadow,
  backgroundColor: theme.palette.background.paper,
  boxSizing: 'border-box',
  margin: 0,
}));

export const TempCardContent = styled(Box)({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  height: '100%',
});

export const TempValueContainer = styled(Box)({
  display: 'flex',
  alignItems: 'baseline',
});

export const TempValue = styled(Typography)({
  fontWeight: 'bold',
  fontSize: '2.2rem',
  color: colors.tileValue,
});

export const TempUnit = styled(Typography)({
  marginLeft: 4,
  color: colors.tileValue,
});
