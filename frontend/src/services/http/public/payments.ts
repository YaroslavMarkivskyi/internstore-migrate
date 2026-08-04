import { ccApi as api } from '@services/http/api';

interface PaymentIntentRaw {
  clientSecret: string;
}

// Mirrors orders.PaymentIntentRead (services/orders/src/orders/schemas.py).
// Only valid for orders placed with paymentMethod "card" and currently
// "pending" -- see routers/payments.py's create_payment_intent for the
// full guard list.
export const createPaymentIntent = async (orderId: string): Promise<string> => {
  const resp = await api.post<PaymentIntentRaw>(
    `orders/orders/${orderId}/payment-intent`
  );
  return resp.data.clientSecret;
};
