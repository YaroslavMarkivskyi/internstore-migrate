import { memo } from 'react';

import { Typography } from '@mui/material';

import colors from '@constants/colors';

import { StatCardContainer, StatValue } from './styles';

export interface StatCardProps {
  title: string;
  value: string | number;
}

const StatCard = memo(({ title, value }: StatCardProps) => (
  <StatCardContainer>
    <Typography
      variant="subtitle1"
      color={colors.tileText}
      component="h3"
      aria-label={title}
    >
      {title}
    </Typography>
    <StatValue variant="h2" aria-label={`${value}`}>
      {value}
    </StatValue>
  </StatCardContainer>
));

StatCard.displayName = 'StatCard';

export default StatCard;
