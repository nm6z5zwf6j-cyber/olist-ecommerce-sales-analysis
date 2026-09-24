# Processed data

Run `python -m src.analysis` from the repository root to rebuild this directory.

The repository keeps compact summary tables and a 1,000-row sample. The complete generated `sales_analysis.csv` is excluded from Git to keep the repository lightweight. It is recreated from the original Olist tables whenever the pipeline runs.

Revenue in this project means the sum of item prices for delivered orders. Freight is not included.

