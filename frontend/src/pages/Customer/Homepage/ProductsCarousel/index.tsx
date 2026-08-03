import { useNavigate } from 'react-router';

import { Typography } from '@mui/material';
import Carousel from 'react-multi-carousel';
import 'react-multi-carousel/lib/styles.css';

import ProductCard from '@components/UI/customer/ProductCard';

import ArrowButton from './customButtons';
import { CarouselResponsiveness } from './styles';

import { IProductPublic } from 'src/types/products/interfaces';

interface ProductsCarouselProps {
  title: string;
  products: IProductPublic[];
  loading: boolean;
  error: string | null;
}

const ProductsCarousel: React.FC<ProductsCarouselProps> = ({
  title,
  products,
  loading,
  error,
}) => {
  const navigate = useNavigate();

  const handleProductClick = (productId: string) => {
    return () => navigate(`/products/${productId}`);
  };

  return (
    <>
      <Typography>{title}</Typography>
      {loading ? (
        <Typography>Loading</Typography>
      ) : (
        <>
          <Carousel
            responsive={CarouselResponsiveness}
            swipeable={false}
            draggable={false}
            customLeftArrow={<ArrowButton direction="left" />}
            customRightArrow={<ArrowButton direction="right" />}
            containerClass="carousel-container"
            itemClass="carousel-item-padding"
          >
            {products.map(product => (
              <ProductCard
                key={product.id}
                product={product}
                onClick={handleProductClick(product.id)}
              />
            ))}
          </Carousel>
        </>
      )}
      {error ?? <Typography>{error}</Typography>}
    </>
  );
};

export default ProductsCarousel;
