import { useRef } from 'react';

import { useNavigate, useOutletContext, useParams } from 'react-router';

import { CircularProgress } from '@mui/material';

import Pagination from '@components/UI/common/Pagination';
import ProductCard from '@components/UI/customer/ProductCard';
import ProductsFilters from '@pages/Customer/CategoryPage/components/ProductsFilters';
import useFilterProducts from '@pages/Customer/CategoryPage/hooks/useFilterProducts';

import { CategoryContextType } from '../CategoryMenu';

import useItemsPerPage from '../../../hooks/useItemsPerPage';

import { PageContent, ProductsContainer, Subtitle, Title } from './styles';

const CategoryPage = () => {
  const { categoryId } = useParams();
  const { categories } = useOutletContext<CategoryContextType>();
  const navigate = useNavigate();
  const category = categories?.find(c => c.id === categoryId);
  const containerRef = useRef<HTMLDivElement>(null);

  const itemsPerPage = useItemsPerPage(containerRef, 200, 15, 3);

  const {
    products,
    page,
    count,
    priceMax,
    priceMin,
    setPage,
    setFilters,
    isLoading,
    deleteFilter,
    ordering,
  } = useFilterProducts(itemsPerPage, categoryId ?? '');

  const isFiltersApplied = priceMax || priceMin || ordering;

  const handleProductCardClick = (productId: string) => {
    navigate('/products/' + productId);
  };

  return (
    <PageContent ref={containerRef}>
      <Title>{category?.name}</Title>
      {isLoading ? (
        <CircularProgress sx={{ m: 'auto' }} />
      ) : (
        <>
          <ProductsFilters
            setFilters={setFilters}
            deleteFilter={deleteFilter}
            ordering={ordering}
            priceMax={priceMax}
            priceMin={priceMin}
          />
          {!products.length ? (
            <Subtitle>
              {isFiltersApplied
                ? 'No products found'
                : 'There are no products in the category yet'}
            </Subtitle>
          ) : (
            <>
              <ProductsContainer>
                {products.map(product => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    showCart={true}
                    onClick={handleProductCardClick}
                  />
                ))}
              </ProductsContainer>
              <Pagination
                sx={{ mx: 'auto' }}
                count={Math.ceil(count / itemsPerPage)}
                page={page}
                onChange={(_e, p) => setPage(p)}
              />
            </>
          )}
        </>
      )}
    </PageContent>
  );
};

export default CategoryPage;
