"""Start the full OwnableFit application."""

from app import app, get_csrf_token, require_csrf_token, seed_products
from src.admin_routes import register_admin_routes
from src.customer_routes import register_customer_routes


# Both sets of routes use the same session and form-token helpers.
register_customer_routes(
    app,
    get_csrf_token,
    require_csrf_token,
)

register_admin_routes(
    app,
    get_csrf_token,
    require_csrf_token,
    seed_products,
)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)