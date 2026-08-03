import { memo } from 'react';

import useFilterProducts from '../../../../../hooks/useFilterProducts';
import { ProductOrderingPositive } from '../../../../../types/products/types';

import ProductsFilters from './components/ProductsFilters';
import ProductsHeader from './components/ProductsHeader';
import ProductsPagination from './components/ProductsPagination';
import ProductsTable from './components/ProductsTable';
import { ProductsContainer } from './styles';

const ProductsContent = () => {
  const limit = 8;
  const {
    products,
    count,
    ordering,
    page,
    priceMin,
    priceMax,
    totalQuantityMin,
    totalQuantityMax,
    category,
    isPublished,
    setFilters,
    isLoading,
    deleteFilter,
    setPage,
    refresh,
    setData,
  } = useFilterProducts(limit);

  const handleChangeOrdering = (newOrdering: ProductOrderingPositive) => {
    if (ordering === newOrdering) {
      setFilters({ ordering: `-${newOrdering}` });
    } else {
      setFilters({ ordering: newOrdering });
    }
  };

  const totalPages = Math.ceil(count / limit);

  return (
    <ProductsContainer>
      <ProductsHeader />
      <ProductsFilters
        deleteFilter={deleteFilter}
        setFilters={setFilters}
        priceMin={priceMin}
        priceMax={priceMax}
        totalQuantityMin={totalQuantityMin}
        totalQuantityMax={totalQuantityMax}
        category={category}
        isPublished={isPublished}
      />
      <ProductsTable
        products={products}
        setOrdering={handleChangeOrdering}
        isLoading={isLoading}
        refresh={refresh}
        setProducts={setData}
      />
      {totalPages > 1 && (
        <ProductsPagination
          count={totalPages}
          currentPage={page}
          onPageChange={p => setPage(p)}
        />
      )}
    </ProductsContainer>
  );
};

export default memo(ProductsContent);
