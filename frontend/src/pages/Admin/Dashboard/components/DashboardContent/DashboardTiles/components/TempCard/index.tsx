import { memo } from 'react';

import { Typography } from '@mui/material';

import colors from '@constants/colors';

import {
  TempCardContainer,
  TempCardContent,
  TempUnit,
  TempValue,
  TempValueContainer,
} from './styles';

export interface TemperatureCardProps {
  store: string;
  temp: number;
}
const TemperatureCard = memo(({ store, temp }: TemperatureCardProps) => (
  <TempCardContainer>
    <TempCardContent>
      <Typography
        variant="subtitle1"
        color={colors.tileText}
        component="h3"
        aria-label={`Temperature at ${store}`}
      >
        Temperature at {store}
      </Typography>
      <TempValueContainer aria-label={`${temp} degrees`}>
        <TempValue variant="h3">{temp}</TempValue>
        <TempUnit variant="h4">°</TempUnit>
      </TempValueContainer>
    </TempCardContent>
  </TempCardContainer>
));

TemperatureCard.displayName = 'TemperatureCard';

export default TemperatureCard;
