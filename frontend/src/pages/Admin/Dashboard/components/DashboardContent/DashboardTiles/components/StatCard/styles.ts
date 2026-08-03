import { Card, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

import { cardStyle } from '../../../styles';

export const StatCardContainer = styled(Card)(({ theme }) => ({
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

export const StatValue = styled(Typography)(({ theme }) => ({
  marginTop: theme.spacing(2),
  fontWeight: 'bold',
  fontSize: '2.5rem',
  color: colors.tileValue,
  textAlign: 'right',
  width: '100%',
}));
