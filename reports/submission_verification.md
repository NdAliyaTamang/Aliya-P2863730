# OwnableFit submission verification

Verified on 12 November 2026 with Python 3.12.14 on Linux and the pinned web dependencies.

| Check | Result |
|---|---|
| Fresh installation | Dependencies installed and `pip check` passed |
| Existing automated suite | 60 of 60 tests passed |
| Local startup | `python run.py` served the shop and admin sign-in pages over HTTP |
| Recommendation | The existing integration test passed with the real exported model |
| Sustainability | Existing calculator and scenario comparison tests passed |
| Accounts and order access | Registered and signed in, signed out and back in, and confirmed order history persisted. A separate client received HTTP 404 for the same order |
| Storefront and checkout | Searched for a newly created dress, added a size to the cart, checked form-token enforcement, completed checkout, and reviewed the order |
| Simulated payment | Exercised decline, cancellation, and success. The paid order had a confirmation and its items were cleared from the cart |
| Admin catalogue | Checked sign-in protection, signed in, created a dress, edited stock, and confirmed the archived dress became unavailable in the storefront |

Account, admin, and checkout checks used Flask's test client with fresh SQLite data and synthetic test records.

## Known limits

- Checkout simulates payments. Stock quantities are maintained manually.
- Recommendations return dataset size codes for model-linked items. Newly created products use manual size selection. Retail size conversion and the traditional size-chart comparison remain unresolved.
- Sustainability estimates depend on user-entered assumptions. Actual returns and emissions reductions have yet to be measured.
- Full browser compatibility, physical-device testing, screen-reader testing, and accessibility verification remain open.
- Research notebook reproduction remains unverified for this submission.
