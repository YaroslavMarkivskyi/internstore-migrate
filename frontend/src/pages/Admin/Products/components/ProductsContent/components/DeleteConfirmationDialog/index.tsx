import { FC, RefObject } from 'react';

import CloseIcon from '@mui/icons-material/Close';
import {
  Box,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
} from '@mui/material';

import ButtonAdmin from '@components/UI/admin/ButtonAdmin';

import { DeleteConfirmationDialog as StyledDeleteConfirmationDialog } from './styles';

import { IProductAdmin } from 'src/types/products/interfaces';

interface DeleteConfirmationDialogProps {
  open: boolean;
  product: IProductAdmin;
  onClose: () => void;
  onConfirm: () => void;
  toastRef: RefObject<HTMLDivElement | null>;
  isLoading: boolean;
}

const DeleteConfirmationDialog: FC<DeleteConfirmationDialogProps> = ({
  open,
  product,
  onClose,
  onConfirm,
  toastRef,
  isLoading,
}) => {
  return (
    <StyledDeleteConfirmationDialog open={open} onClose={onClose}>
      <IconButton
        aria-label="close"
        onClick={onClose}
        sx={{
          position: 'absolute',
          right: 8,
          top: 8,
          color: 'primary.main',
        }}
      >
        <CloseIcon />
      </IconButton>
      <DialogTitle id="delete-dialog-title">
        Are you sure you want to delete this product?
      </DialogTitle>

      <DialogContent>
        <Box display="flex" alignItems="center" gap={2} justifyContent="center">
          {product?.image && (
            <Box
              component="img"
              src={product.image}
              alt={product.name}
              sx={{
                width: 64,
                height: 64,
                objectFit: 'cover',
                borderRadius: 1,
              }}
            />
          )}
          <Typography variant="body1">{product.name}</Typography>
        </Box>
      </DialogContent>

      <DialogActions
        sx={{ justifyContent: 'center', gap: 2, pb: 3 }}
        ref={toastRef}
      >
        <ButtonAdmin
          variant="outlined"
          fullWidth
          disabled={isLoading}
          onClick={onClose}
        >
          No
        </ButtonAdmin>
        <ButtonAdmin
          variant="contained"
          fullWidth
          disabled={isLoading}
          onClick={onConfirm}
        >
          Yes
        </ButtonAdmin>
      </DialogActions>
    </StyledDeleteConfirmationDialog>
  );
};

export default DeleteConfirmationDialog;
