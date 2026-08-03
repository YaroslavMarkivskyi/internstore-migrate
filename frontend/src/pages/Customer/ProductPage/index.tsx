import { FC, useEffect, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';

import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ShoppingCartOutlinedIcon from '@mui/icons-material/ShoppingCartOutlined';
import { Box, Button, Container, Paper, Typography } from '@mui/material';

import { getProduct as getProductAdmin } from '@services/http/admin/products';
import { getCartItem } from '@services/http/public/cart';
import { getProduct as getProductPublic } from '@services/http/public/products';
import { addRecentProductId } from '@store/reducers/recentViewedProducts';
import { useDispatch } from '@store/store';
import { isAdmin } from '@utils/isAdmin';

import RecentlyViewedProducts from '../Homepage/RecentlyViewedProducts';

import LoadingSpinner from '../../../components/UI/common/LoadingSpinner';
import { useCart } from '../../../hooks/useCart';
import {
  IProductAdmin,
  IProductPublic,
} from '../../../types/products/interfaces';

import { styles } from './styles';

interface ProductPageProps {
  area: 'admin' | 'customer';
}

const ProductPage: FC<ProductPageProps> = ({ area }) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<IProductPublic | IProductAdmin | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dispatch = useDispatch();

  const { addToCart, cartItemsIds, setCartItemsIds } = useCart();
  const isInCart = id && cartItemsIds.has(id);

  const handleAddToCartClick = async () => {
    if (!product) return;
    await addToCart(product.id);
  };

  useEffect(() => {
    const fetchProduct = async () => {
      if (!id) return;

      setLoading(true);
      setError(null);

      // Check if item in cart
      try {
        if (!cartItemsIds.has(id)) {
          // getCartItem resolves to undefined (not a rejection) when the
          // product isn't in the cart -- only actually add it to
          // cartItemsIds when it was found, otherwise every product page
          // visited gets marked "already in cart" on first load.
          const cartItem = await getCartItem(id);
          if (cartItem) {
            setCartItemsIds(prevState => {
              const newSet = new Set(prevState);
              newSet.add(id);
              return newSet;
            });
          }
        }
      } catch {
        // Network/cart-fetch error -- leave cartItemsIds as-is.
      }

      try {
        const methodsMap = {
          admin: getProductAdmin,
          customer: getProductPublic,
        };
        const productData = await methodsMap[area](id);
        setProduct(productData);

        if (area === 'customer') {
          dispatch(addRecentProductId(productData.id));
        }
      } catch (err) {
        console.error('Error fetching product:', err);
        setError('Product not found or is not currently available.');
      } finally {
        setLoading(false);
      }
    };

    fetchProduct();
  }, [id]);

  if (loading) {
    return (
      <Box sx={styles.loadingContainer}>
        <LoadingSpinner />
      </Box>
    );
  }

  if (error || !product) {
    return (
      <Container maxWidth="lg" sx={styles.errorContainer}>
        <Box sx={styles.errorContent}>
          <Typography variant="h4" gutterBottom>
            Product Not Found
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            {error ||
              'The product you are looking for does not exist or is not currently available.'}
          </Typography>
          <Button
            variant="contained"
            onClick={() => navigate('/')}
            sx={styles.errorButton}
          >
            Go to Homepage
          </Button>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={styles.container}>
      <Paper elevation={2} sx={styles.paper}>
        <Box sx={styles.productLayout}>
          {/* Product Image */}
          <Box sx={styles.imageContainer}>
            <Box sx={styles.imageBox}>
              {product.image ? (
                <img
                  src={product.image}
                  alt={product.name}
                  style={styles.image}
                />
              ) : (
                <Typography variant="body1" color="text.secondary">
                  No image available
                </Typography>
              )}
            </Box>
          </Box>

          {/* Product Details */}
          <Box sx={styles.detailsContainer}>
            <Typography
              variant="h4"
              component="h1"
              gutterBottom
              sx={styles.title}
            >
              {product.name}
            </Typography>

            {/* Price and Add to Cart Button Row */}
            <Box sx={styles.priceAndButtonRow}>
              <Typography variant="h5" sx={styles.price}>
                ${product.price}
              </Typography>

              {/* Add to Cart Button - Only show for non-admin users */}
              {!isAdmin() && !isInCart && (
                <Box sx={styles.addToCartContainer}>
                  <Button
                    variant="contained"
                    size="medium"
                    sx={styles.addToCartButtonWithColors}
                    endIcon={<ShoppingCartOutlinedIcon />}
                    onClick={handleAddToCartClick}
                  >
                    Add to Cart
                  </Button>
                </Box>
              )}
              {isInCart && (
                <Box sx={styles.addToCartContainer}>
                  <Button
                    variant="contained"
                    size="medium"
                    sx={styles.addToCartButtonWithColors}
                    endIcon={<CheckCircleOutlineIcon />}
                    disabled
                  >
                    Added to cart
                  </Button>
                </Box>
              )}
            </Box>

            <Typography variant="h6" gutterBottom>
              Description
            </Typography>
            <Typography variant="body1" sx={{ mb: 2 }}>
              {product.description}
            </Typography>
          </Box>
        </Box>
      </Paper>

      <RecentlyViewedProducts />
    </Container>
  );
};

export default ProductPage;
