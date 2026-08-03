import { FC, forwardRef } from 'react';

import { ButtonProps } from '@mui/material';

import { ButtonBase } from './styles';

/** Base Button for Customer UI Kit */
const ButtonCustomer: FC<ButtonProps> = forwardRef<
  HTMLButtonElement,
  ButtonProps
>((props, ref) => {
  return <ButtonBase {...props} ref={ref} />;
});

export default ButtonCustomer;
