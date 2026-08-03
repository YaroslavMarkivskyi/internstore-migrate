import { FC } from 'react';

import CustomIcon, {
  CustomIconPartialProps,
} from '@components/UI/icons/CustomIcon';

import icon from './icon.svg';

const OrdersIcon: FC<CustomIconPartialProps> = ({ className }) => {
  return <CustomIcon src={icon} className={className} alt="orders" />;
};

export default OrdersIcon;
