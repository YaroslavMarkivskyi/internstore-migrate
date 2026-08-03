import React, { useEffect, useRef, useState } from 'react';

import CloseIcon from '@mui/icons-material/Close';
import { Stack } from '@mui/material';

import { ErrorText } from '@components/auth/styles';
import {
  distributeProducts,
  getStock,
  getStocks,
} from '@services/http/admin/stocks';
import showToast from '@utils/showToast';

import AddDestinationButton from './components/AddDestinationBtn';
import CancelButton from './components/CancelButton';
import SaveButton from './components/SaveButton';
import TransferItem from './components/TransferItem';
import {
  getAvailableStocksForItem,
  handleAddTransferItem,
  handleQuantityChange,
  handleStockChange,
} from './functions';
import {
  MoveFromInput,
  MoveToStockText,
  MoveToStockTitle,
  QuantityInput,
  StyledMoveToStockCloseButton,
  StyledMoveToStockContainer,
} from './styles';
import { validateTransfers } from './validation';

import {
  IStockProduct,
  ProductsDistribution,
  Stock,
  TransferUnit,
} from 'src/types/stocks/interfaces';

export interface TransferItemData {
  stockId: number | null;
  quantity: number;
}

interface MoveToStockMenuProps {
  sourceStockId: number;
  productStockEntry: IStockProduct;
  onClose: () => void;
  onSuccess?: () => void;
}

const blankTransferItem: TransferItemData = { stockId: null, quantity: 0 };

const MoveToStockMenu: React.FC<MoveToStockMenuProps> = ({
  sourceStockId,
  productStockEntry,
  onClose = () => console.log('closed'),
  onSuccess,
}) => {
  const [sourceStock, setSourceStock] = useState<Stock>();
  const [allStocks, setAllStocks] = useState<Stock[]>([]);
  const [transferItems, setTransferItems] = useState<TransferItemData[]>([
    blankTransferItem,
  ]);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const toastAnchorEl = useRef(null);

  // Fetch source stock and all available stocks
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get source stock details
        const stock = await getStock(sourceStockId);
        setSourceStock(stock);

        // Get all available stocks
        const stocks = await getStocks();
        // Filter out the source stock from available stocks
        const availableStocks = stocks.filter(s => s.id !== sourceStockId);
        setAllStocks(availableStocks);
      } catch (error) {
        console.error('Error fetching stocks:', error);
      }
    };

    if (sourceStockId) {
      fetchData();
    }
  }, [sourceStockId]);

  // Handler for saving the transfer
  const handleSave = async () => {
    // Run validation checks
    const error = validateTransfers(transferItems, productStockEntry);
    if (error) {
      setValidationError(error);
      return;
    }

    // Clear any previous validation errors
    setValidationError(null);

    // Prepare payload for API
    const transfers: TransferUnit[] = transferItems.map(item => ({
      targetStock: item.stockId as number,
      quantityToTransfer: item.quantity,
    }));

    const payload: ProductsDistribution = { transfers };

    try {
      setIsLoading(true);
      if (!productStockEntry.id) {
        return;
      } // TODO: temporary solution, need to be refactored with separate type
      await distributeProducts(payload, sourceStockId, productStockEntry.id);
      showToast({
        message: 'Saved successfully',
        type: 'success',
        anchorEl: toastAnchorEl.current,
        autoClose: 1000,
        onClose: () => {
          onSuccess?.();
          onClose();
          setIsLoading(false);
        },
      });
    } catch (error) {
      console.log('Error distributing products:', error);
      setValidationError('An error occurred while saving. Please try again.');
      setIsLoading(false);
    }
  };

  // Handler for canceling the transfer
  const handleCancel = () => {
    onClose();
    setTransferItems([blankTransferItem]);
    setValidationError(null);
  };

  return (
    <StyledMoveToStockContainer>
      <StyledMoveToStockCloseButton onClick={onClose}>
        <CloseIcon />
      </StyledMoveToStockCloseButton>
      <MoveToStockTitle>Move to stock</MoveToStockTitle>

      <MoveToStockText>Move from</MoveToStockText>
      <Stack direction={'row'} gap={'25px'} sx={{ m: '10px 0' }}>
        <MoveFromInput value={sourceStock?.name} disabled />
        <QuantityInput
          type="number"
          value={productStockEntry?.quantity || 0}
          disabled
        />
      </Stack>

      {/* Transfer Items */}
      {transferItems.map((item, index) => (
        <TransferItem
          key={index}
          availableStocks={getAvailableStocksForItem(
            index,
            transferItems,
            allStocks
          )}
          quantity={item.quantity}
          selectedStockId={item.stockId}
          onQuantityChange={value =>
            handleQuantityChange(index, value, transferItems, setTransferItems)
          }
          onStockChange={value =>
            handleStockChange(index, value, transferItems, setTransferItems)
          }
        />
      ))}

      {/* Validation Error Message */}
      {validationError && (
        <ErrorText color="error">{validationError}</ErrorText>
      )}

      {/* Add new transfer item button - only show if there are available stocks */}
      {transferItems.length < allStocks.length && (
        <AddDestinationButton
          onClick={() => handleAddTransferItem(transferItems, setTransferItems)}
        />
      )}

      {/* Action buttons */}
      <Stack
        ref={toastAnchorEl}
        direction={'row'}
        gap={'25px'}
        sx={{ mt: '20px' }}
      >
        <CancelButton onClick={handleCancel} isDisabled={isLoading} />
        <SaveButton onClick={handleSave} isDisabled={isLoading} />
      </Stack>
    </StyledMoveToStockContainer>
  );
};

export default MoveToStockMenu;
