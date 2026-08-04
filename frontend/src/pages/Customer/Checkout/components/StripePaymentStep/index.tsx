import { useEffect, useRef, useState } from 'react';

import { Box, Button, Typography } from '@mui/material';
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { isAxiosError } from 'axios';

import LoadingSpinner from '@components/UI/common/LoadingSpinner';
import { createPaymentIntent } from '@services/http/public/payments';
import showToast from '@utils/showToast';

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// checkout() returns as soon as the Order row is written with status "new"
// -- the new -> pending flip (stock actually reserved) happens
// asynchronously off a Kafka event a moment later (see
// consumers/inventory_events.py's handle_stock_reserved), and
// POST .../payment-intent 409s until that lands. Retrying covers that
// ordinary saga lag. The worst case is longer than it looks: Inventory's
// outbox worker (which publishes StockReserved after actually reserving
// stock) only polls every RESERVATION_CHECK_INTERVAL_SECONDS -- 5s in
// docker-compose.yml -- stacked on top of Orders' own ~1s
// OUTBOX_POLL_INTERVAL_SECONDS for publishing OrderCreated in the first
// place. ~13s of budget comfortably clears that ~6s worst case with
// margin; if it's still 409ing after that, something's actually wrong
// (e.g. reservation failed outright) and this gives up and surfaces it
// like any other error.
const MAX_PAYMENT_INTENT_ATTEMPTS = 26;
const PAYMENT_INTENT_RETRY_DELAY_MS = 500;

const createPaymentIntentWithRetry = async (orderId: string): Promise<string> => {
  for (let attempt = 1; attempt <= MAX_PAYMENT_INTENT_ATTEMPTS; attempt++) {
    try {
      return await createPaymentIntent(orderId);
    } catch (error) {
      const isLastAttempt = attempt === MAX_PAYMENT_INTENT_ATTEMPTS;
      if (isLastAttempt || !isAxiosError(error) || error.response?.status !== 409) {
        throw error;
      }
      await sleep(PAYMENT_INTENT_RETRY_DELAY_MS);
    }
  }
  // Unreachable -- the loop above always returns or throws.
  throw new Error('createPaymentIntentWithRetry: exhausted retries without a result');
};

// process.env.STRIPE_PUBLISHABLE_KEY (not import.meta.env) -- vite.config.ts
// strips the VITE_ prefix and re-exposes every VITE_* var this way, same as
// SERVER_URL in services/http/api.ts. Loaded once at module scope per
// Stripe's own guidance (loadStripe should not be called on every render).
const stripePromise = loadStripe(process.env.STRIPE_PUBLISHABLE_KEY ?? '');

interface PaymentFormProps {
  onPaid: () => void;
  onSkip: () => void;
}

const PaymentForm = ({ onPaid, onSkip }: PaymentFormProps) => {
  const stripe = useStripe();
  const elements = useElements();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePay = async () => {
    if (!stripe || !elements) return;

    setIsSubmitting(true);
    // redirect: 'if_required' -- the PaymentIntent is created card-only
    // (routers/payments.py), so there's no redirect-based method in play
    // and this stays on the page instead of needing a return_url.
    const { error } = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });
    setIsSubmitting(false);

    if (error) {
      showToast({
        message: error.message ?? 'Payment failed, please try again',
        type: 'error',
      });
      return;
    }

    showToast({ message: 'Payment successful!', type: 'success' });
    onPaid();
  };

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <PaymentElement />
      <Box display="flex" gap={2}>
        <Button
          variant="contained"
          disabled={!stripe || isSubmitting}
          onClick={handlePay}
        >
          Pay
        </Button>
        <Button variant="text" disabled={isSubmitting} onClick={onSkip}>
          Pay later
        </Button>
      </Box>
    </Box>
  );
};

interface StripePaymentStepProps {
  orderId: string;
  onPaid: () => void;
  onSkip: () => void;
}

// Order stays "pending" (reserved but unpaid) until either this confirms
// payment or the reservation TTL expires it back to cancelled -- see
// services/inventory/src/inventory/reservation_expiry.py. "Pay later"
// leaves it exactly there, same end state as a cash_on_delivery order that
// hasn't been confirmed by an admin yet.
const StripePaymentStep = ({ orderId, onPaid, onSkip }: StripePaymentStepProps) => {
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  // StrictMode double-invokes effects on mount in dev (mount -> cleanup ->
  // mount again) -- without this guard, that fires
  // createPaymentIntentWithRetry twice concurrently for the same orderId,
  // and the second call collides with the first's Stripe idempotency key
  // (create_payment_intent's options={"idempotency_key":
  // f"order-{order_id}-payment-intent"} in stripe_client.py) with a 500
  // instead of a clean retry. The `cancelled` flag alone doesn't prevent
  // this: it only stops the *stale* invocation's result from being applied
  // after the fact, the underlying HTTP call has already gone out by then.
  const hasStartedRef = useRef(false);
  // A ref (not a `let cancelled` local closed over per-effect-run) because
  // hasStartedRef makes the *second* StrictMode invocation a no-op that
  // never re-registers its own promise handlers -- if `cancelled` lived in
  // that second invocation's closure instead, the only request that's
  // actually in flight (the first invocation's) would still see the first
  // invocation's cleanup flip its *own* `cancelled` to true (StrictMode
  // runs that cleanup immediately after the first mount) and its
  // successful response would be silently dropped, leaving this stuck on
  // "Preparing payment..." forever despite the payment intent having been
  // created server-side. Resetting this ref to false on every effect run
  // (including the second, no-op one) keeps it in sync with the *current*
  // mount instead of the stale first one.
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    if (!hasStartedRef.current) {
      hasStartedRef.current = true;
      createPaymentIntentWithRetry(orderId)
        .then(secret => {
          if (!cancelledRef.current) setClientSecret(secret);
        })
        .catch(() => {
          if (!cancelledRef.current) {
            showToast({
              message: 'Could not start payment, please try again',
              type: 'error',
            });
            onSkip();
          }
        });
    }

    return () => {
      cancelledRef.current = true;
    };
  }, [orderId]);

  if (!clientSecret) {
    return (
      <Box display="flex" flexDirection="column" alignItems="center" gap={2}>
        <LoadingSpinner />
        <Typography>Preparing payment...</Typography>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <Typography variant="h6">Enter card details</Typography>
      <Elements stripe={stripePromise} options={{ clientSecret }}>
        <PaymentForm onPaid={onPaid} onSkip={onSkip} />
      </Elements>
    </Box>
  );
};

export default StripePaymentStep;
