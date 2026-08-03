import { useEffect } from 'react';

import { useNavigate } from 'react-router-dom';

import { zodResolver } from '@hookform/resolvers/zod';
import { Divider, Grid, Typography } from '@mui/material';
import axios from 'axios';
import { useForm } from 'react-hook-form';

import { checkout } from '@services/http/public/orders';
import { parseApiErrors } from '@utils/parseAPIErrors';
import showToast from '@utils/showToast';

import CartDetails from '../CartDetails';
import ContactInfo, { PAYMENT_METHODS } from '../ContactInfo';

import { useCart } from '../../../../../hooks/useCart';
import { ICartItem } from '../../../../../types/cart/interfaces';
import { CheckoutFormData, checkoutSchema } from '../../validation';

import { CheckoutContent, CheckoutWrapper } from './styles';

// Mirrors orders.CheckoutInsufficientStockResponse
// (services/orders/src/orders/schemas.py) -- camelCased by ccApi's
// response transformer same as every other API response.
interface InsufficientStockItem {
  productId: string;
  requested: number;
  available: number;
  sufficient: boolean;
}

// The 409 body only carries product_id/requested/available, not a name --
// look the name up from the cart items already held client-side so the
// message is actionable ("Milk: only 10 available") instead of a bare
// "insufficient stock for one or more items".
const buildInsufficientStockMessage = (
  items: InsufficientStockItem[],
  cartItems: ICartItem[]
): string => {
  const lines = items
    .filter(item => !item.sufficient)
    .map(item => {
      const name =
        cartItems.find(cartItem => cartItem.product.id === item.productId)
          ?.product.name ?? 'Item';
      return `${name}: only ${item.available} available (requested ${item.requested})`;
    });
  return lines.length > 0
    ? `Not enough stock -- ${lines.join('; ')}`
    : 'Insufficient stock for one or more items';
};

const CheckoutBase = () => {
  const navigate = useNavigate();
  const { register, handleSubmit, formState, watch, setValue } =
    useForm<CheckoutFormData>({
      resolver: zodResolver(checkoutSchema),
      mode: 'onChange',
      defaultValues: { paymentMethod: PAYMENT_METHODS[0].value },
    });
  const {
    items: cartItems,
    isLoading: cartLoading,
    hasMore,
    fetchCartItems,
    fetchCart,
    totalCost,
  } = useCart();

  const paymentMethod = watch('paymentMethod');

  useEffect(() => {
    void fetchCartItems({ offset: 0 }, true);
  }, []);

  useEffect(() => {
    // Guards against landing here directly with nothing in the cart --
    // does not fire on the very first render, since useCart's isLoading
    // starts true until the fetch above resolves.
    if (!cartLoading && cartItems.length === 0) {
      navigate('/');
    }
  }, [cartLoading, cartItems]);

  const onSubmit = async (data: CheckoutFormData) => {
    try {
      await checkout({
        contactName: data.contactName,
        contactEmail: data.contactEmail,
        contactPhone: data.contactPhone || undefined,
        paymentMethod: data.paymentMethod,
      });
      // The backend clears the cart's items server-side as part of
      // checkout (services/orders/src/orders/routers/checkout.py) -- no
      // separate "clear cart" call, just refetch to reflect that.
      await fetchCart();
      await fetchCartItems({ offset: 0 }, true);
      showToast({ message: 'Order placed successfully!', type: 'success' });
      navigate('/');
    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        err.response?.status === 409 &&
        Array.isArray(err.response.data?.items)
      ) {
        showToast({
          message: buildInsufficientStockMessage(
            err.response.data.items,
            cartItems
          ),
          type: 'error',
        });
        // Someone else may have bought the remaining stock since this page
        // loaded -- resync quantities rather than leaving a stale view.
        await fetchCartItems({ offset: 0 }, true);
        return;
      }
      showToast({
        message: parseApiErrors(err).root || 'Something went wrong',
        type: 'error',
      });
    }
  };

  return (
    <CheckoutWrapper>
      <Typography my={4}>Checkout</Typography>
      <CheckoutContent>
        <Grid sx={{ xs: 12 }} width="100%">
          <ContactInfo
            register={register}
            formState={formState}
            paymentMethod={paymentMethod}
            onPaymentMethodChange={value =>
              setValue('paymentMethod', value, { shouldValidate: true })
            }
          />
        </Grid>

        <Divider orientation="vertical" flexItem />

        <Grid sx={{ xs: 12 }} width="100%">
          <CartDetails
            products={cartItems}
            isValid={formState.isValid}
            onSubmit={handleSubmit(onSubmit)}
            fetchCartItems={fetchCartItems}
            hasMore={hasMore}
            isLoading={cartLoading || formState.isSubmitting}
            totalCost={totalCost}
          />
        </Grid>
      </CheckoutContent>
    </CheckoutWrapper>
  );
};

export default CheckoutBase;
