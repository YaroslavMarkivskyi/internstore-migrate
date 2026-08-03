import { FC, useEffect, useState } from 'react';

import { useNavigate } from 'react-router';

import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import {
  CircularProgress,
  Fade,
  Modal,
  ModalProps,
  TableBody,
  TableCell,
  TableRow,
} from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import QuantityInput from '@layouts/CustomerLayout/components/Cart/components/QuantityInput';
import {
  CartBadge,
  CartCloseIconButton,
  CartContent,
  CartFooter,
  CartFooterText,
  CartHeader,
  CartIcon,
  CartTable,
  CartTitle,
  CheckoutButton,
  DeleteButton,
  LoadingContainer,
  ModalContent,
  ProductImage,
  SecondaryText,
  TableWrapper,
  TotalWrapper,
} from '@layouts/CustomerLayout/components/Cart/styles';
import { selectCurrentUser } from '@store/reducers/auth';
import { useSelector } from '@store/store';

import { useCart } from '../../../../hooks/useCart';

interface CartProps {
  open: ModalProps['open'];
  onClose: ModalProps['onClose'];
}

const Cart: FC<CartProps> = ({ open, onClose }) => {
  const currentUser = useSelector(selectCurrentUser);
  const navigate = useNavigate();
  const {
    fetchCartItems,
    fetchCart,
    items,
    isLoading,
    hasMore,
    count,
    removeFromCart,
    editQuantity,
    totalCost,
  } = useCart();

  // We need this variable to be able to refetch items if there is no items in view, but there are items in cart
  const [afterDelete, setAfterDelete] = useState(false);

  const handleLoadMore = () => {
    void fetchCartItems({ offset: items.length });
  };

  const handleCheckoutClick = () => navigate('/checkout'); //TODO: Adjust when Checkout page is ready

  const handleQuantityChanged = async (
    recordId: string,
    newQuantity: number
  ) => {
    await editQuantity(recordId, newQuantity);
  };

  const handleDeleteClick = async (recordId: string) => {
    await removeFromCart(recordId);
    setAfterDelete(true);
  };

  useEffect(() => {
    void fetchCartItems({ offset: 0 }, true);
    void fetchCart();
  }, [currentUser]);

  useEffect(() => {
    const hasItemsInCart = count > 0;
    const noItemsInView = items.length === 0;
    if (afterDelete && noItemsInView && hasItemsInCart) {
      void fetchCartItems({ offset: 0 }, true);
    }
    setAfterDelete(false);
  }, [afterDelete, count, items]);

  return (
    <>
      <Modal open={open} onClose={onClose}>
        <ModalContent onClick={e => e.stopPropagation()}>
          <CartHeader>
            <CartTitle>Cart</CartTitle>
            <CartCloseIconButton onClick={() => onClose?.({}, 'escapeKeyDown')}>
              <CloseIcon />
            </CartCloseIconButton>
          </CartHeader>
          <CartContent>
            <TableWrapper>
              {!items.length && (
                <SecondaryText>There is nothing here yet...</SecondaryText>
              )}
              <CartTable>
                <TableBody>
                  {items.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <ProductImage src={item.product.image} />
                      </TableCell>
                      <TableCell>{item.product.name}</TableCell>
                      <TableCell className={'quantity'}>
                        <QuantityInput
                          productPrice={item.product.price}
                          onChange={q =>
                            handleQuantityChanged(item.product.id, q)
                          }
                          defaultValue={item.quantity}
                        />
                      </TableCell>
                      <TableCell className={'price'}>
                        ${item.product.price}
                      </TableCell>
                      <TableCell>
                        <DeleteButton
                          endIcon={<DeleteOutlineOutlinedIcon />}
                          onClick={() => handleDeleteClick(item.product.id)}
                        >
                          Delete
                        </DeleteButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </CartTable>
              {hasMore && (
                <ButtonCustomer
                  onClick={handleLoadMore}
                  variant={'text'}
                  disabled={isLoading}
                  loading={isLoading}
                  sx={{ mx: 'auto' }}
                >
                  {isLoading ? '⠀' : 'Load More'}
                </ButtonCustomer>
              )}
            </TableWrapper>
            <CartFooter>
              <TotalWrapper>
                <CartFooterText>Total:</CartFooterText>
                <CartFooterText>${totalCost ?? '0.00'}</CartFooterText>
              </TotalWrapper>
              <CheckoutButton
                variant={'contained'}
                onClick={handleCheckoutClick}
                disabled={!count}
              >
                Checkout
              </CheckoutButton>
            </CartFooter>
            <Fade in={isLoading} timeout={300}>
              <LoadingContainer>
                <CircularProgress />
              </LoadingContainer>
            </Fade>
          </CartContent>
        </ModalContent>
      </Modal>
      <CartBadge badgeContent={count}>
        <CartIcon />
      </CartBadge>
    </>
  );
};

export default Cart;
