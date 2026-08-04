import { useParams } from 'react-router-dom';

import { Box } from '@mui/material';

import { LoadingIndicator } from '../LoadingIndicator';

import { useModal } from '../../hooks/ModalStockContext';

import { InvalidStockMessage } from './components/InvalidStockMessage';
import { StockTabs } from './components/StockTabs';
import { isValidStockId } from './utils/validateSelectedStock';

import { IStock } from 'src/types/stocks/interfaces';

interface StocksListProps {
  stocks: IStock[];
  loading: boolean;
}

const StocksList = ({ stocks, loading }: StocksListProps) => {
  const { stockId } = useParams<{ stockId: string }>();
  const selectedStock = stockId ?? '';
  const { openModal } = useModal();

  const handleEditClick = (stock: IStock) => {
    openModal({ mode: 'edit', initialData: stock });
  };

  if (loading) {
    return LoadingIndicator();
  }

  if (!isValidStockId(selectedStock, stocks)) {
    return InvalidStockMessage();
  }

  return (
    <Box>
      <StockTabs
        stocks={stocks}
        selectedStock={selectedStock}
        onEditClick={handleEditClick}
      />
    </Box>
  );
};

export default StocksList;
