import { forwardRef, useState } from 'react';

import VisibilityOffOutlinedIcon from '@mui/icons-material/VisibilityOffOutlined';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import { IconButton, InputAdornment } from '@mui/material';

import colors from '../../../../constants/colors';
import { InputFieldProps } from '../../admin/InputFieldAdmin';
import InputFieldCustomer from '../../customer/InputFieldCustomer';

type PasswordFieldProps = Omit<InputFieldProps, 'type' | 'endAdornment'>;

const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  (props, ref) => {
    const [showPassword, setShowPassword] = useState(false);

    const handleClickShowPassword = () => setShowPassword(show => !show);

    return (
      <InputFieldCustomer
        ref={ref}
        {...props}
        type={showPassword ? 'text' : 'password'}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  aria-label={
                    showPassword ? 'hide the password' : 'display the password'
                  }
                  onClick={handleClickShowPassword}
                  edge="end"
                >
                  {showPassword ? (
                    <VisibilityOffOutlinedIcon fill={colors.placeholder} />
                  ) : (
                    <VisibilityOutlinedIcon fill={colors.placeholder} />
                  )}
                </IconButton>
              </InputAdornment>
            ),
          },
        }}
      />
    );
  }
);

export default PasswordField;
