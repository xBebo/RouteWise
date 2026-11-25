# Checkpoint 2 Demo Evidence & Verification Guide (CP2-04)

## 1. Automated Test Execution
Run the full test suite from the project root without touching any developer database (all tests use isolated `tmp_path` SQLite files):

```powershell
pytest -v