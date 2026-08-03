import { memo, useRef, useState } from 'react';

import { CircularProgress } from '@mui/material';

import ProductCard from '@pages/Admin/Stocks/components/ProductCard';

import ProductsPagination from '../Products/components/ProductsContent/components/ProductsPagination';

import StocksList from './components/StockList';
import StockModalForm from './components/StockModalForm';
import StockProductsTable from './components/StockProductsTable';
import StocksFilters from './components/StocksFilters';
import StocksHeader from './components/StocksHeader';
import { ModalProvider } from './hooks/ModalStockContext';
import useFilterStockProducts from './hooks/useFilterStockProducts';
import { useStocks } from './hooks/useStocks';
import { StocksContainer } from './styles';

const AdminStocks = () => {
  const [selectedProductId, setSelectedProductId] = useState<number>();
  const productCardRef = useRef<{ refresh: () => Promise<void> } | null>(null);

  const limit = 8;
  const {
    category,
    priceMin,
    priceMax,
    stockProducts,
    count,
    page,
    setFilters,
    deleteFilter,
    isLoading: isLoadingProducts,
    setPage,
    refresh: refetchProducts,
  } = useFilterStockProducts(limit);
  const {
    stocks,
    loading: isLoadingStocks,
    refetch: refetchStocks,
  } = useStocks();
  const totalPages = Math.ceil(count / limit);

  const handleProductCardRefresh = async () => {
    if (productCardRef.current) {
      await productCardRef.current.refresh();
    }
  };

  return (
    <ModalProvider>
      <StocksContainer>
        <StocksHeader />
        <StocksFilters
          deleteFilter={deleteFilter}
          setFilters={setFilters}
          priceMin={priceMin}
          priceMax={priceMax}
          category={category}
        />
        {selectedProductId && (
          <ProductCard
            ref={productCardRef}
            selectedProductId={selectedProductId}
            refetchProducts={refetchProducts}
            onClose={() => setSelectedProductId(undefined)}
          />
        )}
        <StocksList stocks={stocks} loading={isLoadingStocks} />
        {!isLoadingProducts ? (
          stockProducts && (
            <>
              <StockProductsTable
                stockProducts={stockProducts}
                refetchProducts={refetchProducts}
                selectedProductId={selectedProductId}
                setSelectedProductId={setSelectedProductId}
                onProductCardRefresh={handleProductCardRefresh}
              />
              {totalPages > 1 && (
                <ProductsPagination
                  count={totalPages}
                  currentPage={page}
                  onPageChange={p => setPage(p)}
                />
              )}
            </>
          )
        ) : (
          <CircularProgress sx={{ m: 'auto' }} />
        )}
      </StocksContainer>
      <StockModalForm
        isProducts={stockProducts.some(product => product.quantity > 0)}
        refetchStocks={refetchStocks}
      />
    </ModalProvider>
  );
};

export default memo(AdminStocks);
