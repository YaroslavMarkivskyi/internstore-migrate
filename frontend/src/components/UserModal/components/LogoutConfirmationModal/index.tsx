import React from 'react';

import { DialogTitle, Typography } from '@mui/material';

import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import {
  ModalContainer,
  ModalContent,
  ModalDeleteActions,
} from '@pages/Admin/Stocks/components/StockModalForm/styles';

interface LogoutConfirmationModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const LogoutConfirmationModal: React.FC<LogoutConfirmationModalProps> = ({
  isOpen,
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  return (
    <ModalContainer open={isOpen} onClose={onCancel}>
      <DialogTitle>Confirm Logout</DialogTitle>
      <ModalContent>
        <Typography variant="body1" sx={{ textAlign: 'center' }}>
          You have unsaved changes that will be lost if you log out now. Are you
          sure you want to continue?
        </Typography>
        <ModalDeleteActions>
          <ButtonAdmin
            variant="outlined"
            onClick={onCancel}
            disabled={isLoading}
            fullWidth
          >
            Stay
          </ButtonAdmin>
          <ButtonAdmin
            variant="contained"
            color="error"
            onClick={onConfirm}
            fullWidth
            disabled={isLoading}
          >
            Logout Anyway
          </ButtonAdmin>
        </ModalDeleteActions>
      </ModalContent>
    </ModalContainer>
  );
};

export default LogoutConfirmationModal;
