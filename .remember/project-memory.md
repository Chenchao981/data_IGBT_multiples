# Project Memory

## Iteration Rule

- After each functional adjustment, run the relevant verification, commit the related code/docs, and push to the GitHub remote repository.
- Do not include generated outputs, `__pycache__`, logs, or failed temporary Excel files in commits.

## Current Project Notes

- Jiequn output format is standardized as `NUM + 批次 + parameter columns`.
- Jiequn parameter ordering is centralized in `factories/jiequn/formatting.py`.
- Jiequn CSV parsing uses precise/alias matching in `csv_parser._item_matches_param()`; avoid reverting to broad substring matching.
