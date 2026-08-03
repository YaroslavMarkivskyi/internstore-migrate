import { FC } from 'react';

import {
  CardImage,
  CardPrice,
  CardTitle,
  CardTitleContainer,
  CardWrapper,
  CartIcon,
  CartSecondaryText,
} from '@components/UI/customer/ProductCard/styles';
import colors from '@constants/colors';
import { imagePlaceholderUrl } from '@constants/urls';

import { IProductPublic } from '../../../../types/products/interfaces';

interface ProductCardProps {
  /** Product to display */
  product: IProductPublic;
  /** Action to be called when card is clicked */
  onClick?: (productId: string) => void;
  /** Whether to show cart icon on the bottom right */
  showCart?: boolean;
}

const ProductCard: FC<ProductCardProps> = ({
  product,
  showCart = false,
  onClick,
}) => {
  const handleCardClick = () => {
    onClick?.(product.id);
  };

  return (
    <CardWrapper onClick={handleCardClick}>
      <CardImage src={product.image ? product.image : imagePlaceholderUrl} />
      <CardTitle>{product.name}</CardTitle>
      <CardTitleContainer>
        {product.inStock ? (
          <CardPrice>${product.price}</CardPrice>
        ) : (
          <CartSecondaryText>Out of stock</CartSecondaryText>
        )}
        {showCart && (
          <CartIcon
            sx={{
              color: product.inStock
                ? colors.warning100
                : colors.textDisabled100,
            }}
          />
        )}
      </CardTitleContainer>
    </CardWrapper>
  );
};

export default ProductCard;
