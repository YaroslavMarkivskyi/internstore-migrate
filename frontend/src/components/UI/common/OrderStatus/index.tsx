import { FC } from 'react';

import { BoxProps, capitalize, Typography } from '@mui/material';

import { orderStatusColors } from '@constants/orders';

import { OrderStatus as OrderStatusType } from '../../../../types/orders/types';

import { OrderStatusIndicator, Wrapper } from './styles';

interface OrderStateProps extends BoxProps {
  status: OrderStatusType;
}

const OrderStatus: FC<OrderStateProps> = ({ status, ...rest }) => {
  return (
    <Wrapper {...rest}>
      <OrderStatusIndicator bgcolor={orderStatusColors[status]} />
      <Typography>{capitalize(status)}</Typography>
    </Wrapper>
  );
};

export default OrderStatus;
