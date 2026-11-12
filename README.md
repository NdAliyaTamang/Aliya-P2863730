# OwnableFit

OwnableFit is an academic Flask prototype for women's dress-size recommendations. Customers can browse the catalogue, choose a size, request an optional machine-learning recommendation for a model-linked dress, and complete a simulated checkout. Administrators can add and edit dresses and manage stock by size.

## Install and run

Clone the repository or extract the submission ZIP. Open a terminal in the project folder containing `run.py` and `requirements-web.txt`.

The submission was verified with the pinned dependencies on Python 3.12.14 on Linux.

### macOS and Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-web.txt
.venv/bin/python run.py
```

If you use Python 3.13, use `python3.13` on the first line.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe run.py
```

If you use Python 3.13, use `py -3.13` on the first line.

Leave the terminal running while using the website. Press **Ctrl+C** to stop it.

| Page | Address |
|---|---|
| Customer catalogue | http://127.0.0.1:5001/shop |
| Size recommendation | http://127.0.0.1:5001/ |
| Admin sign-in | http://127.0.0.1:5001/admin/login |
| Model dashboard | http://127.0.0.1:5001/dashboard |
| Model evaluation | http://127.0.0.1:5001/evaluation |
| Sustainability calculator | http://127.0.0.1:5001/sustainability |
| Sustainability scenario comparison | http://127.0.0.1:5001/sustainability/compare |

## SQLite database and admin setup

Starting `run.py` creates `instance/orders.sqlite3` and initializes the required tables. SQLite comes with Python. The database setup code is in `src/order_store.py`, `src/customer_store.py`, `src/admin_store.py`, `src/catalogue_store.py`, and `src/payment_service.py`.

To create an administrator, open a second terminal in the same project folder.

**macOS and Linux**

```bash
.venv/bin/python -m src.admin_store
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m src.admin_store
```

Choose a username and a password of at least 15 characters. Sign in at `/admin/login` and choose **Manage dresses**. You can add a dress, edit its details, set stock for each size, or hide it from the storefront. Setting a size's quantity to zero makes that size unavailable in the shop. Stock is maintained manually.

The application runs locally and simulates payments. Each fresh copy creates its own database and requires its own admin account.

## Test the recommendation

Open the recommendation form and use these demo inputs:

- Dress ID: `1000254`
- Height: `165` cm
- Weight: `62` kg
- Bra-size category: `34b`

The expected result is **dataset size code `8`**. This example checks that the saved model is connected to the web form.

## Run the automated tests

From the project root, use the same virtual environment you used to start the app.

**macOS and Linux**

```bash
.venv/bin/python -m unittest discover -s tests -v
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [submission verification](reports/submission_verification.md) for the latest results and known limits. The suite covers page rendering, prediction integration, invalid inputs, catalogue browsing, order storage, and sustainability calculations.

## Model and data

- `models/ownablefit_export/` contains the trained pipeline, input preparation code, metadata, and evaluation results. Keep these files together and use the model supplied with this project.
- `data/catalogue/` contains the catalogue data used by the website.
- The included model and catalogue are sufficient to run the web app. Research datasets and generated preprocessing outputs are kept outside the submission repository.
- For research reproduction, download the RentTheRunway file from [UC San Diego Clothing Fit Data](https://cseweb.ucsd.edu/~jmcauley/datasets.html#clothing_fit) and extract it as `dataset/renttherunway_final_data.json`. Attach the dataset in Kaggle to run `notebooks/ownablefit.ipynb`, or replace the dataset-discovery code in the notebook's data-loading cell with `dataset_path = Path("../dataset/renttherunway_final_data.json")` when running from the notebook folder. The separate ModCloth inspection script also requires `dataset/modcloth_final_data.json`.
- To regenerate the JSONL preprocessing outputs, run `python src/prepare_dresses.py`, `python src/convert_measurements.py`, and `python src/prepare_adult_data.py` in that order from the project root.
- Dataset citation. Rishabh Misra, Mengting Wan, and Julian McAuley. *Decomposing fit semantics for product size recommendation in metric spaces*. RecSys, 2018.

The model is item-aware logistic regression with `C = 1`. It uses height, weight, reported bra-size category, and dress ID to predict one of 37 dataset size codes. In the customer-grouped held-out evaluation, it achieved **43.73% accuracy** and **0.1639 fixed-label macro F1**. The traditional size-chart comparison and the contract's five-percentage-point threshold remain undetermined.

The recommendation uses the dataset's original size codes. A verified conversion to retail US, EU, or letter sizes is unavailable. Newly added dresses support manual size selection. Model recommendations are available for existing dresses linked to the training dataset.

## Privacy and sustainability

Recommendation measurements are processed in memory and are not saved to SQLite. The database stores account records, catalogue edits, orders, and simulated payment attempts.

The sustainability tools estimate potential returns avoided and emissions savings from user-entered assumptions. The scenarios are hypothetical. The prototype has not measured actual reductions in returns or emissions.

## Troubleshooting

- If the page will not open, check that `run.py` is still running and use port `5001`.
- If `/admin/login` returns 404, stop the server and start it using `run.py`.
- If the model fails to load, check that the files in `models/ownablefit_export/` are present and that you installed `requirements-web.txt` into the environment used to start the app.
