import { useEffect, useState } from 'react';

import { getProducts } from '@services/http/public/products';
import { RootState, useSelector } from '@store/store';

import ProductsCarousel from '../ProductsCarousel';

import { IProductPublic } from 'src/types/products/interfaces';

const RecentlyViewedProducts = () => {
  const productIds = useSelector(
    (state: RootState) => state.recentProducts.productIds
  );
  const [products, setProducts] = useState<IProductPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadProducts = async () => {
      if (productIds.length === 0) {
        setLoading(false);
        return;
      }
      try {
        const query = {
          ids: productIds,
        };
        const res = await getProducts(query);
        const productsMap = new Map(
          res.results.map(product => [product.id, product])
        );
        const orderedProducts = productIds
          .map(id => productsMap.get(id))
          .filter((p): p is IProductPublic => p !== undefined);

        setProducts(orderedProducts);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadProducts();
  }, [productIds]);

  if (!products || products.length === 0) {
    return null;
  }

  return (
    <>
      <ProductsCarousel
        products={products}
        title="Recently Viewed Products"
        loading={loading}
        error={error}
      />
    </>
  );
};

export default RecentlyViewedProducts;
