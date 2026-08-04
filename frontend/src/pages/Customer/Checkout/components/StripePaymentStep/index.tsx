import { useEffect, useState } from 'react';

import { Box, Button, Typography } from '@mui/material';
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';

import LoadingSpinner from '@components/UI/common/LoadingSpinner';
import { createPaymentIntent } from '@services/http/public/payments';
import showToast from '@utils/showToast';

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

  useEffect(() => {
    let cancelled = false;
    createPaymentIntent(orderId)
      .then(secret => {
        if (!cancelled) setClientSecret(secret);
      })
      .catch(() => {
        if (!cancelled) {
          showToast({
            message: 'Could not start payment, please try again',
            type: 'error',
          });
          onSkip();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  if (!clientSecret) return <LoadingSpinner />;

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
