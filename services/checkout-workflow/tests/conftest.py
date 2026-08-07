from checkout_workflow.types import CheckoutWorkflowInput, CheckoutWorkflowItem


def make_input(order_id: str = "order-1", amount: float = 42.0) -> CheckoutWorkflowInput:
    return CheckoutWorkflowInput(
        order_id=order_id,
        owner_id="customer-1",
        contact_name="Ada Lovelace",
        contact_email="ada@example.com",
        contact_phone=None,
        payment_method="card",
        items=[CheckoutWorkflowItem(product_id="product-1", quantity=2)],
        amount=amount,
    )
