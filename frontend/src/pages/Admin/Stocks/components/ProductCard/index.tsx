import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';

import CloseIcon from '@mui/icons-material/Close';
import {
  CircularProgress,
  IconButton,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';

import { imagePlaceholderUrl } from '@constants/urls';
import {
  CloseButtonWrapper,
  ImageContainer,
  ProductCardContainer,
  ProductTitle,
  StocksTable,
  TableWrapper,
} from '@pages/Admin/Stocks/components/ProductCard/styles';
import StockProductMenuPopup from '@pages/Admin/Stocks/components/StockProductMenuPopup';
import getAccidentTimeFormatted from '@pages/Admin/Stocks/utils/getAccidentTimeFormatted';
import { getProduct, getStocksDetails } from '@services/http/admin/products';

import { IProductAdmin } from '../../../../../types/products/interfaces';
import {
  INormalizedProduct,
  IStockDetails,
  IStockProduct,
} from '../../../../../types/stocks/interfaces';

interface ProductCardProps {
  refetchProducts?: () => Promise<void>;
  selectedProductId?: number;
  onClose?: () => void;
}

export interface ProductCardRef {
  refresh: () => Promise<void>;
}

const ProductCard = forwardRef<ProductCardRef, ProductCardProps>(
  ({ selectedProductId, refetchProducts, onClose }, ref) => {
    const [product, setProduct] = useState<IProductAdmin>();
    const [stocksDetails, setStocksDetails] = useState<IStockDetails[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const fetchProduct = async () => {
      if (!selectedProductId) return;
      const productData = await getProduct(String(selectedProductId));
      setProduct(productData);
    };

    const fetchStockDetails = async () => {
      if (!selectedProductId) return;
      const stocksDetailsData = await getStocksDetails(
        String(selectedProductId)
      );
      setStocksDetails(stocksDetailsData.stocks);
    };

    const fetchAll = async () => {
      await fetchProduct();
      await fetchStockDetails();
      setIsLoading(false);
    };

    const refresh = async () => {
      setIsLoading(true);
      await fetchAll();
    };

    useImperativeHandle(ref, () => ({
      refresh,
    }));

    const renderStockDetails = (stockDetails: IStockDetails) => {
      if (!product) return;

      const isTemperatureError =
        stockDetails.temperature > product.maxTemperature ||
        stockDetails.temperature < product.minTemperature;

      const className = isTemperatureError ? 'error' : '';

      const popupProductEntry: IStockProduct = {
        id: stockDetails.id,
        quantity: stockDetails.quantity,
        stockId: stockDetails.stockId,
        product: { id: Number(product.id) } as INormalizedProduct,
      };

      const handleStocksChange = () => {
        void fetchStockDetails();
        void refetchProducts?.();
      };

      return (
        <TableRow key={stockDetails.id}>
          <TableCell className={className}>{stockDetails.name}</TableCell>
          <TableCell className={className}>{stockDetails.quantity}</TableCell>
          <TableCell className={className}>
            {stockDetails.temperature.toFixed(2)}
          </TableCell>
          <TableCell className={className}>
            {isTemperatureError ? getAccidentTimeFormatted() : '-'}
          </TableCell>
          <TableCell>{(stockDetails.humidity * 100).toFixed(2)}%</TableCell>
          <TableCell>-</TableCell>
          <TableCell>
            <StockProductMenuPopup
              product={popupProductEntry}
              onMoveToStockSuccess={handleStocksChange}
              showDuplicateOption={false}
            />
          </TableCell>
        </TableRow>
      );
    };

    useEffect(() => {
      setIsLoading(true);
      void fetchAll();
    }, [selectedProductId]);

    return (
      <ProductCardContainer>
        <CloseButtonWrapper>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </CloseButtonWrapper>

        {isLoading || !product || !stocksDetails ? (
          <CircularProgress sx={{ m: 'auto' }} />
        ) : (
          <>
            <ImageContainer>
              <img
                src={product.image ? product.image : imagePlaceholderUrl}
                alt="Product"
              />
            </ImageContainer>
            <TableWrapper>
              <ProductTitle>{product.name}</ProductTitle>
              <StocksTable>
                <TableHead>
                  <TableRow>
                    <TableCell>Stock</TableCell>
                    <TableCell>Quantity</TableCell>
                    <TableCell>Current t°C</TableCell>
                    <TableCell>Time of t°C incident</TableCell>
                    <TableCell>Current humidity</TableCell>
                    <TableCell>Time of humidity incident</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {stocksDetails.map(stockDetails =>
                    renderStockDetails(stockDetails)
                  )}
                </TableBody>
              </StocksTable>
            </TableWrapper>
          </>
        )}
      </ProductCardContainer>
    );
  }
);

ProductCard.displayName = 'ProductCard';

export default ProductCard;
