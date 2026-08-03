import { useEffect, useState } from 'react';

import { getProducts } from '@services/http/public/products';

import ProductsCarousel from '../ProductsCarousel';

import { IProductPublic } from 'src/types/products/interfaces';

const RecentlyAddedProducts = () => {
  const [products, setProducts] = useState<IProductPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        setLoading(true);
        const res = await getProducts({});
        setProducts(res.results);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  return (
    <>
      <ProductsCarousel
        products={products}
        title="Recently Added Products"
        loading={loading}
        error={error}
      />
    </>
  );
};

export default RecentlyAddedProducts;
