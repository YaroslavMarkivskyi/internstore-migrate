import { z } from 'zod';

// Mirrors orders.CheckoutRequest (services/orders/src/orders/schemas.py):
// one contact_name (no first/last split), no delivery address field at
// all, and payment_method is required -- unlike the upstream design this
// was adapted from, which had first/last/address but no payment method.
export const checkoutSchema = z.object({
  contactName: z.string().min(1, 'Required'),
  contactEmail: z.string().min(1, 'Required').email('Invalid email'),
  contactPhone: z.string().optional(),
  paymentMethod: z.string().min(1, 'Required'),
});

export type CheckoutFormData = z.infer<typeof checkoutSchema>;
