import { useNavigate } from 'react-router-dom';

import {
  Box,
  Divider,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';

import { ProductImage, ProductsTable, ProductsTableWrapper } from './styles';

import { ICartItem } from 'src/types/cart/interfaces';
import { PaginationQueryParams } from 'src/types/pagination/interfaces';

type CartDetailsProps = {
  products: ICartItem[];
  isValid: boolean;
  onSubmit: () => void;
  fetchCartItems: (
    filterParams: Omit<PaginationQueryParams, 'limit'>,
    inplace?: boolean
  ) => Promise<void>;
  hasMore: boolean;
  isLoading: boolean;
  totalCost: string;
};

const CartDetails = ({
  products,
  isValid,
  onSubmit,
  hasMore,
  fetchCartItems,
  isLoading,
  totalCost,
}: CartDetailsProps) => {
  const navigate = useNavigate();

  const handleLoadMore = () => {
    void fetchCartItems({ offset: products.length });
  };

  return (
    <>
      <Typography mb={2}>Cart Details</Typography>

      <ProductsTableWrapper>
        <ProductsTable>
          <TableHead>
            <TableRow>
              <TableCell>Product</TableCell>
              <TableCell>Price</TableCell>
              <TableCell>Quantity</TableCell>
              <TableCell>Sum</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {products.map(item => (
              <TableRow key={item.id}>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={2}>
                    <ProductImage src={item.product.image} />
                    {item.product.name}
                  </Box>
                </TableCell>
                <TableCell>${item.product.price}</TableCell>
                <TableCell>{item.quantity}</TableCell>
                <TableCell>
                  ${(Number(item.product.price) * item.quantity).toFixed(2)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </ProductsTable>
        {hasMore && (
          <Box display="flex" py={1}>
            <ButtonCustomer
              onClick={handleLoadMore}
              variant={'text'}
              disabled={isLoading}
              loading={isLoading}
              sx={{ mx: 'auto' }}
            >
              {isLoading ? '⠀' : 'Load More'}
            </ButtonCustomer>
          </Box>
        )}
      </ProductsTableWrapper>

      <Divider />
      <Box display="flex" justifyContent="space-between" mt={2} mb={4}>
        <Typography>Total</Typography>
        <Typography fontWeight={600}>${totalCost}</Typography>
      </Box>

      <Box display="flex" flexDirection="row-reverse" gap={2} mb={2}>
        <ButtonCustomer
          variant="contained"
          disabled={!isValid || isLoading}
          onClick={onSubmit}
        >
          Confirm Order
        </ButtonCustomer>
        <ButtonCustomer variant="outlined" onClick={() => navigate('/')}>
          Go back shopping
        </ButtonCustomer>
      </Box>
    </>
  );
};

export default CartDetails;
