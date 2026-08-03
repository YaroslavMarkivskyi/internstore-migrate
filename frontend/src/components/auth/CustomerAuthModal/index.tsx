import React, { useState } from 'react';

import { Box } from '@mui/material';

import CustomerLoginComponent from '../CustomerLogin';
import CustomerSignUpComponent from '../CustomerSignUp';

import { PopoverChildProps } from '../../UI/common/SimplePopover';

type AuthView = 'login' | 'register';

export const AuthModal: React.FC<PopoverChildProps> = ({ onRequestClose }) => {
  const [view, setView] = useState<AuthView>('login');

  const switchToRegister = () => setView('register');

  const handleOnClose = () => {
    onRequestClose?.();
  };

  return (
    <Box>
      {view === 'login' ? (
        <CustomerLoginComponent
          switchToSignUp={switchToRegister}
          onClose={handleOnClose}
        />
      ) : (
        <CustomerSignUpComponent onClose={handleOnClose} />
      )}
    </Box>
  );
};
