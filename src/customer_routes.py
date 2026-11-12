"""Customer registration, login, profile and logout for OwnableFit."""

import secrets

from flask import (
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.customer_store import (
    authenticate_customer,
    create_customer,
    get_active_customer,
    init_customer_db,
)


def register_customer_routes(app, get_csrf_token, require_csrf_token):
    """Register customer pages without granting administrator access."""
    init_customer_db()

    def reset_checkout_context():
        """Invalidate shopping forms when customer identity changes."""
        for key in (
            "checkout_token",
            "payment_context",
            "payment_notice",
        ):
            session.pop(key, None)

        session["csrf_token"] = secrets.token_hex(32)

    def end_customer_session():
        """Remove account access and start a new guest session."""
        session.pop("customer_id", None)
        session.pop("customer_name", None)
        session["guest_id"] = secrets.token_hex(32)
        session.pop("cart", None)
        reset_checkout_context()

    @app.before_request
    def resolve_customer():
        """Verify the account before granting account-based access."""
        g.customer = None

        if "customer_id" not in session:
            return None

        # Resolve the session ID against the database before using the account.
        customer = get_active_customer(session.get("customer_id"))

        if customer is None:
            end_customer_session()
            return None

        g.customer = customer
        session["customer_name"] = customer["display_name"]

        # Existing order routes use this ownership identifier.
        # Use the account's stable ownership ID to find orders belonging to this customer.
        owner_id = customer["order_owner_id"]

        if session.get("guest_id") != owner_id:
            session["guest_id"] = owner_id
            reset_checkout_context()

        return None

    def customer_account():
        """Show only the profile associated with the signed-in session."""
        if g.customer is None:
            return redirect(url_for("customer_login"), code=303)

        return render_template(
            "customer_account.html",
            customer=g.customer,
        )

    def customer_register():
        if g.customer is not None:
            return redirect(url_for("customer_account"), code=303)

        error = None
        status = 200
        values = {}

        if request.method == "POST":
            require_csrf_token()

            values = {
                "display_name": request.form.get("display_name", "").strip(),
                "email": request.form.get("email", "").strip(),
            }

            password = request.form.get("password", "")
            confirmation = request.form.get("password_confirmation", "")

            try:
                if password != confirmation:
                    raise ValueError("The passwords do not match.")

                create_customer(
                    display_name=values["display_name"],
                    email=values["email"],
                    password=password,
                )
            except ValueError as validation_error:
                error = str(validation_error)
                status = 400
            else:
                session["customer_account_notice"] = (
                    "Account created successfully. Sign in to continue."
                )
                session["csrf_token"] = secrets.token_hex(32)

                return redirect(
                    url_for("customer_login"),
                    code=303,
                )

        return render_template(
            "customer_register.html",
            csrf_token=get_csrf_token(),
            values=values,
            error=error,
        ), status

    def customer_login():
        if g.customer is not None:
            return redirect(url_for("customer_account"), code=303)

        error = None
        status = 200
        message = session.pop("customer_account_notice", None)

        if request.method == "POST":
            require_csrf_token()

            customer = authenticate_customer(
                request.form.get("email", ""),
                request.form.get("password", ""),
            )

            if customer is None:
                error = (
                    "Unable to sign in. Check your email and password. "
                    "After repeated failed attempts, wait five minutes "
                    "before trying again."
                )
                status = 401
            else:
                session["customer_id"] = customer["customer_id"]
                session["customer_name"] = customer["display_name"]
                session["guest_id"] = customer["order_owner_id"]
                reset_checkout_context()

                # Return to shopping; the profile is opened separately
                # through My account in the navigation.
                return redirect(url_for("shop"), code=303)

        return render_template(
            "customer_login.html",
            csrf_token=get_csrf_token(),
            message=message,
            error=error,
        ), status

    def customer_logout():
        require_csrf_token()
        end_customer_session()

        session["customer_account_notice"] = (
            "You have signed out. Your cart was cleared for privacy."
        )

        return redirect(
            url_for("customer_login"),
            code=303,
        )

    app.add_url_rule(
        "/account",
        endpoint="customer_account",
        view_func=customer_account,
        methods=["GET"],
    )

    app.add_url_rule(
        "/account/register",
        endpoint="customer_register",
        view_func=customer_register,
        methods=["GET", "POST"],
    )

    app.add_url_rule(
        "/account/login",
        endpoint="customer_login",
        view_func=customer_login,
        methods=["GET", "POST"],
    )

    app.add_url_rule(
        "/account/logout",
        endpoint="customer_logout",
        view_func=customer_logout,
        methods=["POST"],
    )