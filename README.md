# RouteWise

Delivery Route Optimizer 

## Sample database

From the repository root, run:

```powershell
python -m scripts.seed_data --reset
```

This replaces locations, roads and route history in `data/routewise.db`, the
same file used by the backend. Back up data you want to keep before resetting.
The loader uses `backend/database/schema.sql`; it does not migrate databases
created with an older or different schema.

To rebuild a separate demonstration database instead:

```powershell
python -m scripts.seed_data --db data/demo.db --reset
```

Only the selected database is reset. CSV input is validated before changing
records, and failed inserts roll back the replacement. Errors identify the
file and row when applicable. Repeated runs recreate the same sample network;
autoincremented internal IDs may change.

Run the backend tests with:

```powershell
python -m pip install -r backend/requirements.txt pytest
python -m pytest
```

Seed tests use temporary databases and never reset the development database.

## Flask API

From the repository root, install and start the backend:

```powershell
python -m pip install -r backend/requirements.txt
python -m backend.app
```

The development server listens at `http://127.0.0.1:5000`.
The locations and roads lists return JSON objects with `locations` or
`roads` array keys. Create and update return a `location` or `road` object.
Successful deletes return HTTP 200 with `{"deleted": true, "id": 1}`.
Errors provide an `error` message and may include a `fields` object.

The Flask app opens a separate SQLite connection for each database operation.
For API tests, set `DB_PATH` to a temporary SQLite file, as the pytest
fixture does.
