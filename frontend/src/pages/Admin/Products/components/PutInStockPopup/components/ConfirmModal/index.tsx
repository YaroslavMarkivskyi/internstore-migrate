import { RefObject } from 'react';

import { Box, Modal, Stack, Typography } from '@mui/material';

import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import { imagePlaceholderUrl } from '@constants/urls';

import { InputField } from '../../styles';
import { StockRow } from '../../types';

interface ConfirmModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  stocks: StockRow[];
  productName?: string;
  productImage?: string;
  toastRef: RefObject<HTMLDivElement | null>;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
  open,
  onClose,
  onConfirm,
  stocks,
  productName,
  productImage,
  toastRef,
}) => {
  return (
    <Modal
      open={open}
      onClose={onClose}
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box
        sx={{
          bgcolor: 'background.paper',
          borderRadius: 2,
          boxShadow: 24,
          p: 4,
          width: 560,
          maxWidth: '100%',
        }}
      >
        <Typography variant="h6" align="center" mb={3}>
          Please confirm putting the item in the stocks below
        </Typography>

        <Stack
          direction="row"
          spacing={3}
          justifyContent="center"
          alignItems="center"
          mb={3}
        >
          <img
            src={productImage ?? imagePlaceholderUrl}
            alt={productName}
            width={60}
          />
          <Typography align="center">{productName}</Typography>
        </Stack>

        {stocks.map((stock, index) => (
          <Stack
            key={index}
            direction="row"
            spacing={3}
            justifyContent="center"
            mb={2}
          >
            <InputField
              fullWidth
              type="text"
              placeholder="Stock"
              value={stock.stock}
              disabled
              sx={{
                maxWidth: 180,
                '& .MuiInputBase-input': {
                  textAlign: 'center',
                },
              }}
            />
            <InputField
              fullWidth
              type="text"
              placeholder="Quantity"
              value={`${stock.quantity} pcs`}
              disabled
              sx={{
                maxWidth: 180,
                '& .MuiInputBase-input': {
                  textAlign: 'center',
                },
              }}
            />
          </Stack>
        ))}

        <Stack
          direction="row"
          spacing={3}
          justifyContent="center"
          ref={toastRef}
        >
          <ButtonAdmin
            variant="outlined"
            onClick={onClose}
            fullWidth
            sx={{ maxWidth: 180 }}
          >
            Cancel
          </ButtonAdmin>
          <ButtonAdmin
            variant="contained"
            onClick={onConfirm}
            fullWidth
            sx={{ maxWidth: 180 }}
          >
            Confirm
          </ButtonAdmin>
        </Stack>
      </Box>
    </Modal>
  );
};

export default ConfirmModal;
