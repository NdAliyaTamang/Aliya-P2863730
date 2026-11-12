"""Register guest order history, simulated payment and confirmation routes."""

import secrets

from flask import (
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.order_store import get_order, list_orders
from src.payment_service import (
    init_payment_db,
    list_payment_attempts,
    order_fingerprint,
    simulate_payment,
)
from src.product_catalogue import format_dkk


def register_payment_routes(app, get_csrf_token, require_csrf_token):
    """Register routes using the application's guest-session protection."""
    init_payment_db()

    def owned_order(order_id):
        """Return an order only to its owning guest."""
        owner_id = session.get("guest_id")
        if not owner_id:
            abort(404)

        order = get_order(order_id, owner_id)
        if order is None:
            abort(404)

        return order

    def my_orders():
        """Show only orders belonging to the current browser's guest."""
        owner_id = session.get("guest_id")

        # Do not create an identity merely to display an empty history.
        orders = list_orders(owner_id) if owner_id else []

        return render_template(
            "orders.html",
            orders=orders,
            format_dkk=format_dkk,
        )

    def matching_cart(order):
        """Avoid clearing a cart changed after checkout."""
        cart = session.get("cart", [])

        if not isinstance(cart, list):
            return False

        try:
            current = sorted(
                (item["product_id"], item["size"], item["quantity"])
                for item in cart
            )
            ordered = sorted(
                (
                    item["product_id"],
                    item["selected_size"],
                    item["quantity"],
                )
                for item in order["items"]
            )
        except (KeyError, TypeError):
            return False

        return current == ordered

    def payment(order_id):
        order = owned_order(order_id)

        if request.method == "POST":
            require_csrf_token()

        if order["status"] == "paid":
            return redirect(
                url_for("order_confirmation", order_id=order_id),
                code=303,
            )

        if order["status"] != "pending_payment":
            abort(409, description="This order is not awaiting payment.")

        error = None
        status = 200
        outcome = None

        if request.method == "POST":
            context = session.get("payment_context", {})
            supplied = request.form.get("payment_token", "")

            if (
                not isinstance(context, dict)
                or context.get("order_id") != order_id
                or not isinstance(context.get("token"), str)
                or not secrets.compare_digest(context["token"], supplied)
            ):
                abort(
                    400,
                    description=(
                        "The payment form expired. "
                        "Reload the payment page and try again."
                    ),
                )

            try:
                attempt = simulate_payment(
                    order_id=order_id,
                    owner_id=session["guest_id"],
                    request_token=context["token"],
                    outcome=request.form.get("outcome", ""),
                    expected_fingerprint=context.get("fingerprint"),
                )
            except ValueError as validation_error:
                error = str(validation_error)
                status = 400
            else:
                if attempt["outcome"] == "success":
                    if matching_cart(order):
                        session.pop("cart", None)
                        session.pop("checkout_token", None)

                    session.pop("payment_context", None)

                    return redirect(
                        url_for(
                            "order_confirmation",
                            order_id=order_id,
                        ),
                        code=303,
                    )

                session["payment_notice"] = {
                    "order_id": order_id,
                    "outcome": attempt["outcome"],
                }

                return redirect(
                    url_for("payment", order_id=order_id),
                    code=303,
                )

        if request.method == "GET":
            notice = session.pop("payment_notice", None)

            if (
                isinstance(notice, dict)
                and notice.get("order_id") == order_id
            ):
                outcome = notice.get("outcome")

        if request.method == "GET" or error:
            order = owned_order(order_id)

            if order["status"] == "paid":
                return redirect(
                    url_for("order_confirmation", order_id=order_id),
                    code=303,
                )

            if order["status"] != "pending_payment":
                abort(409, description="This order is not awaiting payment.")

            # Save a request token and a fingerprint of the order shown on the payment page.
            session["payment_context"] = {
                "order_id": order_id,
                "token": secrets.token_hex(32),
                "fingerprint": order_fingerprint(order),
            }

        return render_template(
            "payment.html",
            order=order,
            csrf_token=get_csrf_token(),
            payment_token=session["payment_context"]["token"],
            format_dkk=format_dkk,
            error=error,
            outcome=outcome,
        ), status

    def order_confirmation(order_id):
        order = owned_order(order_id)

        attempts = list_payment_attempts(
            order_id,
            session["guest_id"],
        )
        successful = [
            attempt
            for attempt in attempts
            if attempt["outcome"] == "success"
        ]

        # Visiting confirmation cannot create a successful payment.
        if order["status"] != "paid" or not successful:
            return redirect(
                url_for("order_review", order_id=order_id),
                code=303,
            )

        return render_template(
            "order_confirmation.html",
            order=order,
            payment_attempt=successful[0],
            format_dkk=format_dkk,
        )

    app.add_url_rule(
        "/orders",
        endpoint="my_orders",
        view_func=my_orders,
        methods=["GET"],
    )

    app.add_url_rule(
        "/orders/<order_id>/payment",
        endpoint="payment",
        view_func=payment,
        methods=["GET", "POST"],
    )

    app.add_url_rule(
        "/orders/<order_id>/confirmation",
        endpoint="order_confirmation",
        view_func=order_confirmation,
        methods=["GET"],
    )