OwnableFit prototype model

Python version used: 3.13.15

Files
- ownablefit_pipeline.joblib: fitted preprocessing and classifier
- input_preparation.py: formats inputs for the pipeline
- model_metadata.json: environment and model details
- requirements.txt: Python package versions
- test_results*.csv: aggregate evaluation results

Raw input columns
height_cm, weight_kg, bra_size, item_id

Use metric measurements and preserve item IDs as their original text.
Call prepare_item_inputs before pipeline.predict.
Missing values are handled by the fitted preprocessing.

Output
A dataset size code, without a verified US/EU conversion.
The prediction is not a guarantee of fit.

Evaluation limitations
Traditional size-chart comparison remains unresolved.
Evaluation mainly concerns new customers on known dresses.
Actual return reduction has not been measured.

Dataset source
https://www.kaggle.com/datasets/rmisra/clothing-fit-dataset-for-size-recommendation
Source dataset licence: CC BY 4.0
https://creativecommons.org/licenses/by/4.0/

Research
Misra, R., Wan, M. and McAuley, J. (2018).
Decomposing fit semantics for product size recommendation in metric spaces.
https://doi.org/10.1145/3240323.3240398

Only load trusted joblib files.
