import { TransferItemData } from '.';

import { IStockProduct } from 'src/types/stocks/interfaces';

// Validate transfers and return validation error message if any
export const validateTransfers = (
  transferItems: TransferItemData[],
  productStockEntry: IStockProduct
): string | null => {
  // check for non selected stocks
  const nullableDestinationStocks = transferItems.filter(
    item => item.stockId === null
  );

  if (nullableDestinationStocks.length > 0) {
    return 'Please select a destination stock.';
  }

  // Check if any transfer item has zero quantity
  const hasZeroQuantityItem = transferItems.some(
    item => item.stockId !== null && item.quantity === 0
  );

  if (hasZeroQuantityItem) {
    return 'One or more stock transfers have 0 quantity. Please enter a quantity or remove the transfer.';
  }

  // Check if total quantity exceeds source stock quantity
  const totalTransferQuantity = transferItems.reduce(
    (sum, item) => sum + (item.quantity || 0),
    0
  );

  if (totalTransferQuantity > (productStockEntry?.quantity || 0)) {
    return `Total transfer quantity (${totalTransferQuantity}) exceeds available quantity (${productStockEntry?.quantity || 0}).`;
  }

  return null;
};
