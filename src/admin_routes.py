"""Protected admin pages for order overview and catalogue management."""

import secrets
import time
from functools import wraps

from flask import abort, flash, g, redirect, render_template, request, session, url_for

from src.admin_store import authenticate_admin, get_active_admin, init_admin_db
from src.catalogue_store import catalogue_by_id, product_from_form, save_product
from src.order_store import database
from src.payment_service import init_payment_db
from src.product_catalogue import SIZE_ORDER, filter_products, format_dkk


# Require sign-in again after 30 minutes of inactivity on admin pages.
ADMIN_IDLE_SECONDS = 30 * 60


def load_dashboard_data():
    """Read order totals and recent orders without customer contact details."""
    with database() as connection:
        counts = connection.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(
                    CASE WHEN status = 'pending_payment' THEN 1 ELSE 0 END
                ), 0) AS pending_orders,
                COALESCE(SUM(
                    CASE WHEN status = 'paid' THEN 1 ELSE 0 END
                ), 0) AS paid_orders,
                COALESCE(SUM(
                    CASE WHEN status = 'paid' THEN total_minor ELSE 0 END
                ), 0) AS paid_total_minor
            FROM orders
        """).fetchone()

        attempt_count = connection.execute(
            "SELECT COUNT(*) FROM payment_attempts"
        ).fetchone()[0]

        recent = connection.execute("""
            SELECT order_id, created_at, status, delivery_label, total_minor
            FROM orders
            ORDER BY created_at DESC, order_id DESC
            LIMIT 20
        """).fetchall()

    stats = dict(counts)
    stats["payment_attempts"] = attempt_count
    return stats, [dict(order) for order in recent]


def register_admin_routes(app, get_csrf_token, require_csrf_token, seed_products):
    """Connect the admin pages to the main OwnableFit app."""
    init_admin_db()
    init_payment_db()

    def clear_admin_session():
        session.pop("admin_id", None)
        session.pop("admin_last_seen", None)

    def current_admin():
        """Check the account and session expiry on each protected request."""
        admin_id = session.get("admin_id")
        last_seen = session.get("admin_last_seen")
        now = int(time.time())

        if (
            type(admin_id) is not int
            or type(last_seen) is not int
            or last_seen > now
            or now - last_seen > ADMIN_IDLE_SECONDS
        ):
            clear_admin_session()
            return None

        # Check the stored account status on each protected request.
        admin = get_active_admin(admin_id)
        if admin is None:
            clear_admin_session()
            return None

        session["admin_last_seen"] = now
        return admin

    def admin_required(view):
        """Apply the same sign-in check to every protected admin route."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            admin = current_admin()
            if admin is None:
                return redirect(url_for("admin_login"), code=303)

            g.admin = admin
            return view(*args, **kwargs)

        return wrapped

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "GET" and current_admin() is not None:
            return redirect(url_for("admin_dashboard"), code=303)

        error = None
        status = 200

        if request.method == "POST":
            require_csrf_token()
            # Verify the submitted username and password before granting admin access.
            admin = authenticate_admin(
                request.form.get("username", ""),
                request.form.get("password", ""),
            )

            if admin is None:
                error = (
                    "Unable to sign in. Check your credentials. "
                    "After repeated failed attempts, wait five minutes "
                    "before trying again."
                )
                status = 401
            else:
                session["admin_id"] = admin["admin_id"]
                session["admin_last_seen"] = int(time.time())

                # Replace the form token when the user gains admin access.
                session["csrf_token"] = secrets.token_hex(32)
                return redirect(url_for("admin_dashboard"), code=303)

        return render_template(
            "admin_login.html",
            csrf_token=get_csrf_token(),
            error=error,
        ), status

    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        stats, recent_orders = load_dashboard_data()
        return render_template(
            "admin_dashboard.html",
            admin=g.admin,
            stats=stats,
            recent_orders=recent_orders,
            format_dkk=format_dkk,
            csrf_token=get_csrf_token(),
        )

    @app.get("/admin/catalogue")
    @admin_required
    def admin_catalogue():
        """Show visible and archived dresses in a searchable list."""
        query = request.args.get("q", "").strip()[:100]
        products = filter_products(
            catalogue_by_id(seed_products).values(),
            {"q": query},
        )
        page_size = 25
        last_page = max(1, (len(products) + page_size - 1) // page_size)
        page = max(1, min(request.args.get("page", 1, type=int), last_page))
        start = (page - 1) * page_size

        return render_template(
            "admin_catalogue.html",
            products=products[start:start + page_size],
            count=len(products),
            query=query,
            page=page,
            last_page=last_page,
            format_dkk=format_dkk,
        )

    @app.route("/admin/catalogue/new", methods=["GET", "POST"])
    @app.route("/admin/catalogue/<product_id>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_product(product_id=None):
        """Use one form for both new dresses and existing dresses."""
        if product_id is None:
            product = {"size_stock": {}, "is_sample": True}
        else:
            product = catalogue_by_id(seed_products).get(product_id)
            if product is None:
                abort(404)

        sizes = tuple(dict.fromkeys((*SIZE_ORDER, *product["size_stock"])))
        revision = str(product.get("revision", 0))
        price = product.get("price_minor", 0)
        values = {
            **product,
            "price": f"{price // 100}.{price % 100:02d}",
            "occasions": ", ".join(product.get("occasions", [])),
            **{
                f"stock_{size}": product["size_stock"].get(size, 0)
                for size in sizes
            },
        }
        error = None
        status = 200

        if request.method == "POST":
            require_csrf_token()

            # Preserve entered values if the administrator needs to fix a field.
            values = {
                **request.form,
                "archived": request.form.get("archived") == "on",
            }
            # Read the revision from the opened form to detect a newer edit before saving.
            revision = request.form.get("revision", "")

            try:
                # Validate the submitted price and size quantities before saving.
                updated = product_from_form(request.form, product)
                saved_id = save_product(updated, revision)
            except ValueError as exc:
                error = str(exc)
                status = 400
            else:
                flash("Dress saved.")
                return redirect(
                    url_for("admin_product", product_id=saved_id),
                    code=303,
                )

        return render_template(
            "admin_product.html",
            product_id=product_id,
            values=values,
            sizes=sizes,
            revision=revision,
            csrf_token=get_csrf_token(),
            error=error,
        ), status

    @app.post("/admin/logout")
    def admin_logout():
        require_csrf_token()
        clear_admin_session()
        session["csrf_token"] = secrets.token_hex(32)
        return redirect(url_for("admin_login"), code=303)