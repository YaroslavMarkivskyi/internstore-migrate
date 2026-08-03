import { TargetStock } from './components/TransferItem';

import { TransferItemData } from '.';

import { Stock } from 'src/types/stocks/interfaces';

type setTransferItemsType = (
  value: React.SetStateAction<TransferItemData[]>
) => void;

// Get available stocks for a specific transfer item
export const getAvailableStocksForItem = (
  currentItemIndex: number,
  transferItems: TransferItemData[],
  allStocks: Stock[]
): TargetStock[] => {
  const selectedStockIds = transferItems
    .filter((_, index) => index !== currentItemIndex && _.stockId !== null)
    .map(item => item.stockId);

  return allStocks
    .filter(stock => !selectedStockIds.includes(stock.id))
    .map(stock => ({ id: stock.id, name: stock.name }));
};

// Handler for adding a new transfer item
export const handleAddTransferItem = (
  transferItems: TransferItemData[],
  setTransferItems: setTransferItemsType
) => {
  setTransferItems([...transferItems, { stockId: null, quantity: 0 }]);
};

// Handler for changing the selected stock in a transfer item
export const handleStockChange = (
  index: number,
  stockId: number | null,
  transferItems: TransferItemData[],
  setTransferItems: setTransferItemsType
) => {
  setTransferItems(
    transferItems.map((item, i) => (i === index ? { ...item, stockId } : item))
  );
};

export const handleQuantityChange = (
  index: number,
  quantity: number,
  transferItems: TransferItemData[],
  setTransferItems: setTransferItemsType
) => {
  const validQuantity = Math.max(0, quantity);
  setTransferItems(
    transferItems.map((item, i) =>
      i === index ? { ...item, quantity: validQuantity } : item
    )
  );
};
