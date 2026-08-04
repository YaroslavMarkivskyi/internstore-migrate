import { Dispatch, memo, SetStateAction, useState } from 'react';

import { Table, TableBody } from '@mui/material';

import StockProductRow from './components/StockProductRow';
import StockTableHeader from './components/TableHeader';
import { TableBox, TableContainer } from './styles';

import { IStockProduct } from 'src/types/stocks/interfaces';

interface Props {
  stockProducts: IStockProduct[];
  refetchProducts: () => Promise<void>;
  selectedProductId?: string;
  setSelectedProductId: Dispatch<SetStateAction<string | undefined>>;
  onProductCardRefresh?: () => Promise<void>;
}

const StockProductsTable = ({
  stockProducts,
  refetchProducts,
  selectedProductId,
  setSelectedProductId,
  onProductCardRefresh,
}: Props) => {
  const [editingProductId, setEditingProductId] = useState<
    string | undefined
  >();

  const handleStartEditing = (productId: string) => {
    setEditingProductId(productId);
  };

  const handleFinishEditing = () => {
    setEditingProductId(undefined);
  };

  const handleUpdateSuccess = async () => {
    await refetchProducts();
    if (onProductCardRefresh) {
      await onProductCardRefresh();
    }
  };

  return (
    <TableBox>
      <TableContainer>
        <Table>
          <StockTableHeader />
          <TableBody>
            {stockProducts.map(product => (
              <StockProductRow
                key={product.product.id}
                stockProduct={product}
                refetchProducts={refetchProducts}
                selectedProductId={selectedProductId}
                setSelectedProductId={setSelectedProductId}
                isEditing={editingProductId === product.product.id}
                onStartEditing={handleStartEditing}
                onFinishEditing={handleFinishEditing}
                onUpdateSuccess={handleUpdateSuccess}
              />
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </TableBox>
  );
};

export default memo(StockProductsTable);
