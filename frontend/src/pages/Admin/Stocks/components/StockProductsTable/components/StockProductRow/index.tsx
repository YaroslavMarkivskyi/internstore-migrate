import { Dispatch, SetStateAction } from 'react';

import { TableCell } from '@mui/material';

import QuantityCellContainer from '../QuantityCellContainer';

import StockProductMenuPopup from '../../../StockProductMenuPopup';

import {
  ActionsCell,
  ProductImage,
  ProductNameCell,
  StyledTableRow,
} from './styles';

import { IStockProduct } from 'src/types/stocks/interfaces';

interface Props {
  stockProduct: IStockProduct;
  isEditing: boolean;
  onStartEditing: (productId: number) => void;
  onFinishEditing: () => void;
  onUpdateSuccess: () => Promise<void>;
  refetchProducts: () => Promise<void>;
  selectedProductId?: number;
  setSelectedProductId: Dispatch<SetStateAction<number | undefined>>;
}

const StockProductRow = ({
  stockProduct,
  refetchProducts,
  selectedProductId,
  setSelectedProductId,
  isEditing,
  onStartEditing,
  onFinishEditing,
  onUpdateSuccess,
}: Props) => {
  const { product, quantity, id } = stockProduct;

  const handleClick = () => {
    setSelectedProductId(product.id);
  };

  return (
    <StyledTableRow
      className={selectedProductId === product.id ? 'selected-row' : ''}
      key={product.id}
      onClick={handleClick}
    >
      <TableCell>{product.id}</TableCell>
      <TableCell>
        <ProductImage src={product.image} alt={product.name} />
      </TableCell>
      <TableCell>
        <ProductNameCell>{product.name}</ProductNameCell>
      </TableCell>
      <TableCell>{product.category}</TableCell>
      <TableCell>$ {product.price}</TableCell>
      <TableCell>{product.minTemperature}</TableCell>
      <TableCell>{product.maxTemperature}</TableCell>
      <TableCell>
        {id ? (
          <QuantityCellContainer
            productEntryId={id}
            isEditing={isEditing}
            quantity={quantity}
            onUpdateSuccess={onUpdateSuccess}
            onEditComplete={onFinishEditing}
          />
        ) : (
          quantity
        )}
      </TableCell>
      <ActionsCell>
        {id && (
          <StockProductMenuPopup
            product={stockProduct}
            onEditQuantity={() => onStartEditing(product.id)}
            onMoveToStockSuccess={refetchProducts}
          />
        )}
      </ActionsCell>
    </StyledTableRow>
  );
};

export default StockProductRow;
