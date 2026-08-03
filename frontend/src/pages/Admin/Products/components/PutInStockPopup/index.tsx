import { FC, useEffect, useRef, useState } from 'react';

import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import RadioButtonCheckedIcon from '@mui/icons-material/RadioButtonChecked';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import {
  Box,
  InputAdornment,
  SelectChangeEvent,
  Stack,
  Typography,
} from '@mui/material';

import { StyledIconButton } from '@components/auth/styles';
import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import colors from '@constants/colors';
import { bulkAddStocks, getStocks } from '@services/http/admin/stocks';
import showToast from '@utils/showToast';

import { IProductAdmin } from '../../../../../types/products/interfaces';

import ConfirmModal from './components/ConfirmModal';
import {
  ChooseField,
  ChooseFieldMenuItem,
  InputField,
  PopupContainer,
  PutInStockTitle,
} from './styles';
import { StockRow } from './types';

interface PutInStockModalProps {
  open: boolean;
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onConfirm: (newCount: number) => void;
  product: IProductAdmin;
}

interface Stock {
  id: number;
  name: string;
}

const PutInStockPopup: FC<PutInStockModalProps> = ({
  open,
  anchorEl,
  onClose,
  onConfirm,
  product,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [rows, setRows] = useState<StockRow[]>([{ stock: '', quantity: '' }]);
  const [error, setError] = useState<string | null>(null);
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);

  const toastAnchorEl = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      const fetchStocks = async () => {
        try {
          const data = await getStocks();
          setStocks(data);
          if (data.length > 0) {
            setRows([{ stock: data[0].name, quantity: 0 }]);
          }
        } catch {
          onClose();
        }
      };

      fetchStocks();
    }
  }, [open]);

  const handleChange = (event: SelectChangeEvent<unknown>, index: number) => {
    const newRows = [...rows];
    newRows[index].stock = event.target.value as string;
    setRows(newRows);
  };

  const handleQuantityChange = (value: number, index: number) => {
    const newRows = [...rows];
    newRows[index].quantity = value;
    setRows(newRows);
  };

  const handleAddRow = () => {
    const usedStocks = rows.map(row => row.stock);
    const nextStock = stocks.find(stock => !usedStocks.includes(stock.name));

    if (nextStock) {
      setRows([...rows, { stock: nextStock.name, quantity: 0 }]);
    }
  };

  const handleDeleteRow = (index: number) => {
    const newRows = rows.filter((_, i) => i !== index);
    setRows(newRows);
  };

  const handleOpenConfirmModal = () => {
    const validRows = rows.filter(
      row => row.stock && row.quantity !== '' && Number(row.quantity) > 0
    );

    if (validRows.length === 0) {
      setError('At least one stock must have quantity greater than 0');
      return;
    }

    setError(null);
    setConfirmModalOpen(true);
  };

  const handleSave = async () => {
    try {
      setIsLoading(true);

      const transfers = rows
        .filter(
          row => row.stock && row.quantity !== '' && Number(row.quantity) > 0
        )
        .map(row => ({
          target_stock: stocks.find(s => s.name === row.stock)?.id || 0,
          quantity_to_transfer: Number(row.quantity),
        }));

      await bulkAddStocks({
        product_id: Number(product.id),
        transfers,
      });
      showToast({
        message: 'Product added to stock(s) successfully',
        type: 'success',
        anchorEl: toastAnchorEl.current,
        autoClose: 1000,
        onClose: () => {
          const quantityToAdd = transfers.reduce(
            (sum, item) => sum + item.quantity_to_transfer,
            0
          );
          onClose();
          onConfirm(quantityToAdd);
          setIsLoading(false);
          setConfirmModalOpen(false);
        },
      });
    } catch {
      setError('Failed to update stocks');
      setIsLoading(false);
      setConfirmModalOpen(false);
    }
  };

  return (
    <PopupContainer
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'right',
      }}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'right',
      }}
    >
      <StyledIconButton onClick={onClose} aria-label="close">
        <CloseIcon />
      </StyledIconButton>

      <PutInStockTitle>Put in stock</PutInStockTitle>

      <Stack spacing={2}>
        {rows.map((row, index) => (
          <Stack direction={'row'} gap={3} key={index}>
            <ChooseField
              fullWidth
              value={row.stock}
              onChange={e => handleChange(e, index)}
              renderValue={selected => selected as string}
              MenuProps={{
                PaperProps: {
                  sx: {
                    borderRadius: 2,
                    boxShadow: '0px 6px 18px rgba(0,0,0,0.1)',
                    marginTop: 1.5,
                    '& .MuiList-root': {
                      padding: 0,
                    },
                  },
                },
              }}
            >
              {stocks.map(stock => (
                <ChooseFieldMenuItem key={stock.id} value={stock.name}>
                  {stock.name}
                  {row.stock === stock.name ? (
                    <RadioButtonCheckedIcon />
                  ) : (
                    <RadioButtonUncheckedIcon />
                  )}
                </ChooseFieldMenuItem>
              ))}
            </ChooseField>

            <InputField
              fullWidth
              type="number"
              placeholder="Quantity"
              value={row.quantity}
              onChange={e =>
                handleQuantityChange(Number(e.target.value), index)
              }
              onFocus={e => {
                if (row.quantity === 0) {
                  e.target.select();
                }
              }}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">pcs</InputAdornment>
                  ),
                },
              }}
            />

            {rows.length > 1 && (
              <Box
                sx={{
                  width: 32,
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                }}
              >
                <DeleteOutlineIcon
                  sx={{
                    color: colors.textDisabled200,
                    cursor: 'pointer',
                    '&:hover': {
                      color: colors.error100,
                    },
                  }}
                  onClick={() => handleDeleteRow(index)}
                />
              </Box>
            )}
          </Stack>
        ))}

        <Stack direction={'row'} gap={3}>
          <ButtonAdmin
            fullWidth
            variant="outlined"
            sx={{ minWidth: 160 }}
            onClick={handleAddRow}
          >
            Add more
            <AddIcon sx={{ ml: 1 }} />
          </ButtonAdmin>

          <ButtonAdmin
            fullWidth
            variant="contained"
            disabled={isLoading || rows.length === 0}
            onClick={handleOpenConfirmModal}
            sx={{ minWidth: 160 }}
          >
            Save
          </ButtonAdmin>

          {rows.length > 1 && (
            <Box
              sx={{
                width: 32,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
              }}
            >
              <DeleteOutlineIcon sx={{ color: 'white' }} />
            </Box>
          )}
        </Stack>
      </Stack>
      {error && (
        <Typography
          color="error"
          sx={{
            fontSize: '14px',
            textAlign: 'center',
            mt: 1,
          }}
        >
          {error}
        </Typography>
      )}
      <ConfirmModal
        toastRef={toastAnchorEl}
        open={confirmModalOpen}
        onClose={() => setConfirmModalOpen(false)}
        onConfirm={handleSave}
        stocks={rows.filter(
          row => row.stock && row.quantity !== '' && Number(row.quantity) > 0
        )}
        productName={product.name}
        productImage={product.image}
      />
    </PopupContainer>
  );
};

export default PutInStockPopup;
