import { useNavigate } from 'react-router-dom';

import { TagsWrapper } from '../Products/components/ProductsContent/components/ProductsFilters/styles';
import ProductsFilterTag from '../Products/components/ProductsContent/components/ProductsFilterTag';
import ProductsPagination from '../Products/components/ProductsContent/components/ProductsPagination';
import ProductsTable from '../Products/components/ProductsContent/components/ProductsTable';
import { ProductsContainer } from '../Products/components/ProductsContent/styles';

import useFilterProducts from '../../../hooks/useFilterProducts';

import { NotFoundTitle, SearchTitle } from './styles';

const AdminProductsSearch = () => {
  const navigate = useNavigate();
  const limit = 8;
  const {
    products,
    count,
    page,
    search: searchTerm,
    setPage,
    refresh,
    setData,
  } = useFilterProducts(limit);

  const handleClearQuery = () => {
    navigate('/admin/products');
  };

  if (!searchTerm || count === 0) {
    return <NotFoundTitle>Nothing found...</NotFoundTitle>;
  }

  return (
    <ProductsContainer>
      <TagsWrapper sx={{ mb: 4, alignItems: 'center' }}>
        <SearchTitle>{count} results found</SearchTitle>
        <ProductsFilterTag label={searchTerm} onRemove={handleClearQuery} />
      </TagsWrapper>
      <ProductsTable
        products={products}
        refresh={refresh}
        setProducts={setData}
      />
      <ProductsPagination
        count={Math.ceil(count / limit)}
        currentPage={page}
        onPageChange={setPage}
      />
    </ProductsContainer>
  );
};

export default AdminProductsSearch;
