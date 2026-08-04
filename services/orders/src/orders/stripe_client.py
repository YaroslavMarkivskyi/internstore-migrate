import stripe
from fastapi import Request


class StripeClient:
    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        self._client = stripe.StripeClient(secret_key)
        self._webhook_secret = webhook_secret

    async def create_payment_intent(self, *, amount_cents: int, order_id: str) -> stripe.PaymentIntent:
        return await self._client.v1.payment_intents.create_async(
            {
                "amount": amount_cents,
                "currency": "usd",
                # Card-only -- avoids Stripe's automatic-payment-methods
                # redirect flows (iDEAL, etc.), which would need a
                # return_url the checkout page doesn't have anywhere to
                # send the browser back to.
                "payment_method_types": ["card"],
                "metadata": {"order_id": order_id},
            },
            # Idempotent per order: a retried "create the PaymentIntent for
            # this order" click reuses the same Stripe object instead of
            # minting a duplicate charge target.
            options={"idempotency_key": f"order-{order_id}-payment-intent"},
        )

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        return stripe.Webhook.construct_event(payload, sig_header, self._webhook_secret)


async def get_stripe_client(request: Request) -> StripeClient:
    stripe_client: StripeClient = request.app.state.stripe_client
    return stripe_client
