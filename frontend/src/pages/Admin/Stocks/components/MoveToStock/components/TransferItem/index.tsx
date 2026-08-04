import React from 'react';

import { Radio, Stack } from '@mui/material';

import {
  MoveToStockText,
  QuantityInput,
  TargetStockSelect,
} from '../../styles';

export interface TargetStock {
  id: string;
  name: string;
}

export interface TransferItemProps {
  availableStocks: TargetStock[];
  quantity: number;
  selectedStockId: string | null;
  onQuantityChange: (quantity: number) => void;
  onStockChange: (stockId: string | null) => void;
}

const TransferItem: React.FC<TransferItemProps> = ({
  availableStocks,
  quantity,
  selectedStockId,
  onQuantityChange,
  onStockChange,
}) => {
  // Handler for quantity change
  const handleQuantityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10) || 0;
    onQuantityChange(value);
  };

  // Handler for stock selection change
  const handleStockChange = (value: string | null) => {
    onStockChange(value);
  };

  const clearZeros = (e: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const input = e.target as HTMLInputElement;
    if (parseInt(input.value, 10) === 0) {
      input.value = '';
    }
  };

  return (
    <div>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <MoveToStockText>Move to</MoveToStockText>
      </Stack>

      <Stack
        direction="row"
        justifyContent="center"
        gap="25px"
        sx={{ marginTop: '10px', marginBottom: '20px' }}
      >
        <TargetStockSelect
          value={selectedStockId}
          onChange={e => handleStockChange(String(e.target.value))}
          endComponent={<Radio size="small" />}
          placeholder="Stock"
          options={availableStocks.map(stock => ({
            value: stock.id,
            label: stock.name,
          }))}
        />
        <QuantityInput
          disabled={!selectedStockId}
          type="number"
          value={quantity}
          onChange={handleQuantityChange}
          onClick={clearZeros}
        />
      </Stack>
    </div>
  );
};

export default TransferItem;
