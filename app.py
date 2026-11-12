"""OwnableFit shopping, checkout, simulation and research application."""

import json
import os
import secrets
from pathlib import Path

from flask import (
    Flask, abort, flash, g, redirect, render_template,
    request, session, url_for,
)
from werkzeug.exceptions import HTTPException

from ml_model.model import EXPORT_DIR, get_supported_options
from ml_model.predict import predict_size
from src.cart_service import add_item, get_cart_summary, remove_item
from src.catalogue_store import catalogue_by_id, init_catalogue_db
from src.order_store import (
    CUSTOMER_FIELDS, DELIVERY_OPTIONS,
    create_order, get_order, init_db,
)
from src.payment_routes import register_payment_routes
from src.product_catalogue import (
    SORT_OPTIONS, filter_products, format_dkk,
    get_filter_options, load_display_products,
)
from src.sustainability import calculate_scenario, compare_scenarios


app = Flask(__name__, static_folder="css")
app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def load_secret_key():
    """Reuse the local secret so sessions survive a server restart."""
    configured = os.environ.get("OWNABLEFIT_SECRET_KEY")
    if configured:
        return configured

    directory = Path(app.instance_path)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "session_secret"

    try:
        with path.open("x", encoding="utf-8") as destination:
            key = secrets.token_hex(32)
            destination.write(key)
        path.chmod(0o600)
        return key
    except FileExistsError:
        key = path.read_text(encoding="utf-8").strip()
        if not key:
            raise RuntimeError("The local session key file is empty.")
        return key


app.secret_key = load_secret_key()

dress_ids, bra_sizes = get_supported_options()
supported_dress_ids = set(dress_ids)

# Load the original model-linked dresses once. Admin edits are read separately.
# Keep the original catalogue available when merging saved admin edits.
seed_products = load_display_products()

with (EXPORT_DIR / "model_metadata.json").open(encoding="utf-8") as source:
    metadata = json.load(source)

accuracy_percent = f'{metadata["test_accuracy"] * 100:.2f}'
init_db()
init_catalogue_db()


def current_products():
    """Read the visible catalogue once per customer request."""
    # Reuse one visible catalogue snapshot throughout this request.
    if "shop_products" not in g:
        g.shop_products = {
            product_id: product
            for product_id, product in catalogue_by_id(seed_products).items()
            if not product.get("archived")
        }
    return g.shop_products


def get_csrf_token():
    """Create a token that ties shopping and admin forms to the session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def require_csrf_token():
    # Read the session's token to verify that the submitted form belongs to this browser.
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token", "")

    if (
        not isinstance(expected, str)
        or not secrets.compare_digest(expected, supplied)
    ):
        abort(
            400,
            description="Invalid form session. Reload the page and try again.",
        )


def get_guest_id():
    """Identify the guest without putting contact details in cookies."""
    if "guest_id" not in session:
        session["guest_id"] = secrets.token_hex(32)
    return session["guest_id"]


def invalidate_checkout():
    session.pop("checkout_token", None)


def render_cart_page(error=None, status=200):
    """Render the cart using the current catalogue prices and stock."""
    products = current_products()
    try:
        summary = get_cart_summary(session.get("cart", []), products)
    except ValueError:
        session.pop("cart", None)
        invalidate_checkout()
        summary = get_cart_summary([], products)
        error = "Outdated or invalid cart items were cleared. Please add them again."
        status = 400

    return render_template(
        "cart.html",
        cart_items=summary["items"],
        subtotal_minor=summary["subtotal_minor"],
        total_quantity=summary["total_quantity"],
        format_dkk=format_dkk,
        csrf_token=get_csrf_token(),
        error=error,
    ), status


@app.after_request
def prevent_page_storage(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        dress_count=len(dress_ids),
        bra_size_count=len(bra_sizes),
        size_code_count=len(metadata["size_codes"]),
        model_name=metadata["model"],
        accuracy_percent=accuracy_percent,
    )


@app.get("/shop")
def shop():
    """Show current products, available sizes, filters and page links."""
    display_products = list(current_products().values())
    # Build filter choices from the products customers can currently browse.
    product_options = get_filter_options(display_products)

    fields = (
        "q", "style", "length", "occasion", "colour", "size",
        "min_price", "max_price", "sort",
    )
    filters = {
        field: request.args.get(field, "").strip() for field in fields
    }
    filters["q"] = filters["q"][:100]
    filters["sort"] = filters["sort"] or "name_asc"
    matches = []
    error = None
    status = 200

    try:
        for field, option_key in {
            "style": "styles",
            "length": "lengths",
            "occasion": "occasions",
            "colour": "colours",
            "size": "sizes",
        }.items():
            if filters[field] and filters[field] not in product_options[option_key]:
                raise ValueError(f"Please select a supported {field} option.")

        if filters["sort"] not in SORT_OPTIONS:
            raise ValueError("Please select a supported sorting option.")

        matches = filter_products(display_products, filters)
    except ValueError as validation_error:
        error = str(validation_error)
        status = 400

    total_pages = max(1, (len(matches) + 11) // 12)
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1

    page = max(1, min(page, total_pages))
    start = (page - 1) * 12
    # Keep the selected filters when the customer changes pages.
    active = {key: value for key, value in filters.items() if value}

    return render_template(
        "shop.html",
        products=matches[start:start + 12],
        total_products=len(display_products),
        total_matches=len(matches),
        page=page,
        total_pages=total_pages,
        previous_url=(
            url_for("shop", page=page - 1, **active) if page > 1 else None
        ),
        next_url=(
            url_for("shop", page=page + 1, **active)
            if page < total_pages else None
        ),
        filters=filters,
        options=product_options,
        sort_options=SORT_OPTIONS,
        csrf_token=get_csrf_token(),
        format_dkk=format_dkk,
        error=error,
    ), status


@app.get("/products/<product_id>")
def product_detail(product_id):
    product = current_products().get(product_id)
    if product is None:
        abort(404)

    return render_template(
        "product_detail.html",
        product=product,
        format_dkk=format_dkk,
        csrf_token=get_csrf_token(),
        error=None,
    )


@app.get("/cart")
def cart():
    return render_cart_page()


@app.post("/cart/add")
def add_to_cart():
    """Check the customer's chosen size against the current stock."""
    require_csrf_token()
    product_id = request.form.get("product_id", "")
    products = current_products()
    product = products.get(product_id)
    if product is None:
        abort(404)

    try:
        updated = add_item(
            session.get("cart", []),
            products,
            product_id,
            request.form.get("size", ""),
            request.form.get("quantity", ""),
        )
    except ValueError as validation_error:
        return render_template(
            "product_detail.html",
            product=product,
            format_dkk=format_dkk,
            csrf_token=get_csrf_token(),
            error=str(validation_error),
        ), 400

    # Save the validated size and quantity in this browser's session.
    # Invalidate checkout so an older form cannot submit the changed cart.
    session["cart"] = updated
    invalidate_checkout()
    flash("Item added to your cart.")
    return redirect(url_for("cart"), code=303)


@app.post("/cart/remove")
def remove_from_cart():
    require_csrf_token()
    try:
        session["cart"] = remove_item(
            session.get("cart", []),
            current_products(),
            request.form.get("product_id", ""),
            request.form.get("size", ""),
        )
    except ValueError as validation_error:
        return render_cart_page(str(validation_error), 400)

    invalidate_checkout()
    flash("Item removed from your cart.")
    return redirect(url_for("cart"), code=303)


@app.post("/cart/clear")
def clear_cart():
    require_csrf_token()
    session.pop("cart", None)
    invalidate_checkout()
    flash("Your cart has been cleared.")
    return redirect(url_for("cart"), code=303)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if request.method == "POST":
        require_csrf_token()

    # Check stock again because it may have changed since the cart was opened.
    products = current_products()
    try:
        summary = get_cart_summary(session.get("cart", []), products)
    except ValueError as validation_error:
        return render_cart_page(str(validation_error), 400)

    if not summary["items"]:
        flash("Add an item before continuing to checkout.")
        return redirect(url_for("cart"), code=303)

    # Associate checkout with the current shopper's session ownership ID.
    owner_id = get_guest_id()
    if "checkout_token" not in session:
        session["checkout_token"] = secrets.token_hex(32)

    values = {}
    error = None
    status = 200

    if request.method == "POST":
        # Compare the submitted form with the current checkout session.
        # The database also uses this token to recognize repeated submissions.
        supplied = request.form.get("checkout_token", "")
        if not secrets.compare_digest(session["checkout_token"], supplied):
            abort(
                400,
                description="Checkout changed. Reload checkout and try again.",
            )

        values = {
            field: request.form.get(field, "").strip()
            for field in (*CUSTOMER_FIELDS, "delivery_method")
        }
        try:
            order_id = create_order(
                owner_id=owner_id,
                checkout_token=session["checkout_token"],
                customer={field: values[field] for field in CUSTOMER_FIELDS},
                delivery_method=values["delivery_method"],
                cart=session.get("cart", []),
                products_by_id=products,
            )
        except ValueError as validation_error:
            error = str(validation_error)
            status = 400
        else:
            return redirect(url_for("order_review", order_id=order_id), code=303)

    return render_template(
        "checkout.html",
        cart_items=summary["items"],
        subtotal_minor=summary["subtotal_minor"],
        delivery_options=DELIVERY_OPTIONS,
        format_dkk=format_dkk,
        csrf_token=get_csrf_token(),
        checkout_token=session["checkout_token"],
        values=values,
        error=error,
    ), status


@app.get("/orders/<order_id>")
def order_review(order_id):
    owner_id = session.get("guest_id")
    if not owner_id:
        abort(404)

    # Look up the order using both its reference and the session owner's ID.
    order = get_order(order_id, owner_id)
    if order is None:
        abort(404)

    return render_template(
        "order_review.html",
        order=order,
        format_dkk=format_dkk,
        error=None,
    )


# Register payment pages after defining the shared form-token helpers.
register_payment_routes(app, get_csrf_token, require_csrf_token)


@app.get("/catalogue")
def catalogue():
    """Browse the original dataset IDs used by the recommendation model."""
    query = request.args.get("q", "").strip()[:100]
    match_mode = request.args.get("match", "contains")
    sort_order = request.args.get("sort", "asc")

    if match_mode not in ("contains", "starts"):
        match_mode = "contains"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    matches = [
        item_id for item_id in dress_ids
        if (
            item_id.startswith(query)
            if match_mode == "starts" else query in item_id
        )
    ]

    def dress_sort_key(item_id):
        if item_id.isascii() and item_id.isdigit():
            return (0, int(item_id), item_id)
        return (1, 0, item_id)

    matches.sort(key=dress_sort_key, reverse=(sort_order == "desc"))
    total_pages = max(1, (len(matches) + 11) // 12)

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1

    page = max(1, min(page, total_pages))
    start = (page - 1) * 12

    return render_template(
        "catalogue.html",
        query=query,
        match_mode=match_mode,
        sort_order=sort_order,
        items=matches[start:start + 12],
        page=page,
        total_pages=total_pages,
        total_matches=len(matches),
        total_dresses=len(dress_ids),
    )


@app.get("/evaluation")
def evaluation():
    return render_template(
        "evaluation.html",
        metadata=metadata,
        accuracy_percent=accuracy_percent,
    )


@app.route("/", methods=["GET", "POST"])
def home():
    """Open the optional recommendation form for a supported dataset dress."""
    prediction = None
    result_item_id = None
    selected_item_id = ""
    error = None
    status = 200

    if request.method == "GET":
        # Read a dress ID from the link and check that the model supports it before prefilling.
        candidate = request.args.get("item_id", "").strip()
        if candidate in supported_dress_ids:
            selected_item_id = candidate
        elif candidate:
            error = "Please select a supported dress ID."
            status = 400

    if request.method == "POST":
        try:
            # Pass the measurements directly to the prediction helper.
            # This route returns the result without creating a database record.
            prediction = predict_size(request.form)
            result_item_id = request.form.get("item_id", "").strip()
        except HTTPException:
            raise
        except ValueError as validation_error:
            error = str(validation_error)
            status = 400
        except Exception:
            error = (
                "The prediction could not be completed. "
                "Please try again. If it continues, contact the developer."
            )
            status = 500

    return render_template(
        "index.html",
        dress_ids=dress_ids,
        bra_sizes=bra_sizes,
        selected_item_id=selected_item_id,
        result_item_id=result_item_id,
        prediction=prediction,
        error=error,
    ), status


@app.route("/sustainability", methods=["GET", "POST"])
def sustainability():
    result = None
    error = None
    assumptions = {}
    status = 200

    if request.method == "POST":
        assumptions = {
            field: request.form.get(field, "").strip()
            for field in ("orders", "return_rate", "reduction", "impact")
        }
        try:
            result = calculate_scenario(
                orders=assumptions["orders"],
                size_return_rate_percent=assumptions["return_rate"],
                relative_reduction_percent=assumptions["reduction"],
                kg_co2e_per_return=assumptions["impact"],
            )
        except HTTPException:
            raise
        except ValueError as validation_error:
            error = str(validation_error)
            status = 400
        except Exception:
            error = "The scenario could not be calculated. Please try again."
            status = 500

    return render_template(
        "sustainability.html",
        result=result,
        error=error,
        assumptions=assumptions,
    ), status


@app.route("/sustainability/compare", methods=["GET", "POST"])
def scenario_comparison():
    comparison = None
    error = None
    assumptions = {}
    status = 200

    if request.method == "POST":
        assumptions = {
            field: request.form.get(field, "").strip()
            for field in ("orders", "return_rate", "impact", "low", "medium", "high")
        }
        try:
            comparison = compare_scenarios(
                orders=assumptions["orders"],
                size_return_rate_percent=assumptions["return_rate"],
                low_reduction_percent=assumptions["low"],
                medium_reduction_percent=assumptions["medium"],
                high_reduction_percent=assumptions["high"],
                kg_co2e_per_return=assumptions["impact"],
            )
        except HTTPException:
            raise
        except ValueError as validation_error:
            error = str(validation_error)
            status = 400
        except Exception:
            error = "The comparison could not be calculated. Please try again."
            status = 500

    return render_template(
        "scenario_comparison.html",
        comparison=comparison,
        error=error,
        assumptions=assumptions,
    ), status


@app.errorhandler(413)
def request_too_large(_error):
    message = "The submission is too large. Please complete the form again."

    if request.endpoint in (
        "add_to_cart", "remove_from_cart", "clear_cart", "checkout"
    ):
        return render_cart_page(message, 413)

    if request.endpoint == "payment":
        return (
            "The payment submission is too large. "
            "Return to order review and reopen payment.",
            413,
        )

    if request.endpoint == "admin_product":
        return message, 413

    if request.endpoint == "scenario_comparison":
        return render_template(
            "scenario_comparison.html",
            comparison=None,
            error=message,
            assumptions={},
        ), 413

    if request.endpoint == "sustainability":
        return render_template(
            "sustainability.html",
            result=None,
            error=message,
            assumptions={},
        ), 413

    return render_template(
        "index.html",
        dress_ids=dress_ids,
        bra_sizes=bra_sizes,
        selected_item_id="",
        result_item_id=None,
        prediction=None,
        error=message,
    ), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)