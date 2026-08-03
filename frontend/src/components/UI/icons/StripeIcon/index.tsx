import { FC } from 'react';

import CustomIcon, {
  CustomIconPartialProps,
} from '@components/UI/icons/CustomIcon';

import icon from './icon.svg';

const StripeIcon: FC<CustomIconPartialProps> = props => {
  return <CustomIcon src={icon} alt="stripe" {...props} />;
};

export default StripeIcon;
