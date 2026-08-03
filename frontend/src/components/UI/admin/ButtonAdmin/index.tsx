import { FC, forwardRef } from 'react';

import { ButtonProps } from '@mui/material';

import { ButtonBase } from './styles';

/** Base Button for Admin UI Kit */
const ButtonAdmin: FC<ButtonProps> = forwardRef<HTMLButtonElement, ButtonProps>(
  (props, ref) => {
    return <ButtonBase {...props} ref={ref} />;
  }
);

export default ButtonAdmin;
