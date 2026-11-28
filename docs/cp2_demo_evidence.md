# Checkpoint 2 Demo Evidence & Verification Guide (CP2-04)

## 1. Automated Verification Suite
Run the full test suite from the project root without touching any developer database (all pytest fixtures use isolated `tmp_path` SQLite files):

```powershell
pytest -v
```

To run only the CP2 worked-example and integration tests:

```powershell
pytest backend/tests/test_cp2_worked_example.py -v
```

## 2. Worked Example Catalog Specification
- **Locations:** `D` (Depot), `A`, `B`, `C`, `E` (Customers), plus edge-case nodes `ONEWAY_SRC`, `ONEWAY_DST`, and `ISOLATED`.
- **Roads:** `D-A (4 km)`, `D-B (2 km)`, `B-A (1 km)`, `A-C (5 km)`, `B-C (9 km)`, `B-E (10 km)`, `C-E (2 km)`.
- **Expected Outcomes:**
  1. **Point-to-Point (`D -> E`):** `D -> B -> A -> C -> E` (`10.0 km`).
  2. **Road Closure Detour (`A-C` closed):** `D -> B -> E` (`12.0 km`).
  3. **Same Origin & Destination (`D -> D`):** `[D]`, `0.0 km`.
  4. **One-Way Enforcement:** `ONEWAY_SRC -> ONEWAY_DST` (`3.0 km`) is traversable; reverse direction is blocked.
  5. **Unreachable Destination (`D -> ISOLATED`):** Handled cleanly without server exceptions.
  6. **Multi-Stop Delivery Run (`D` visiting `{B, C, E}`):** Visit order `D -> B -> C -> E` (`10.0 km`).
  7. **Persistence Across Restart:** Saved routes and `route_legs` remain intact when reopening the SQLite database file.

## 3. Live Demo Guide Using a Temporary Database
Follow these steps to load the worked example into an isolated temporary SQLite database (`cp2_demo_temp.db`) so the main developer database (`backend/routewise.db`) remains untouched.

### Step 1: Start the Flask Server on a Temporary Database
In **Terminal 1** (with `.venv` activated), run:

```powershell
python -c "from backend.app import create_app; create_app({'DB_PATH': 'cp2_demo_temp.db'}).run(host='127.0.0.1', port=5000)"
```

### Step 2: Load the Worked Example & Verify Both the 10 km Route and 12 km Detour
In **Terminal 2**, run the following PowerShell script to populate `D, A, B, C, E`, compute the `10.0 km` shortest path, close road `A-C`, and compute the `12.0 km` detour:

```powershell
$base = "[http://127.0.0.1:5000/api](http://127.0.0.1:5000/api)"

# 1. Load Locations (D, A, B, C, E)
$D = (Invoke-RestMethod -Method Post "$base/locations" -ContentType "application/json" -Body '{"code":"D","name":"Depot D","kind":"DEPOT","x":100,"y":500}').location
$A = (Invoke-RestMethod -Method Post "$base/locations" -ContentType "application/json" -Body '{"code":"A","name":"Customer A","kind":"CUSTOMER","x":300,"y":300}').location
$B = (Invoke-RestMethod -Method Post "$base/locations" -ContentType "application/json" -Body '{"code":"B","name":"Customer B","kind":"CUSTOMER","x":300,"y":700}').location
$C = (Invoke-RestMethod -Method Post "$base/locations" -ContentType "application/json" -Body '{"code":"C","name":"Customer C","kind":"CUSTOMER","x":600,"y":300}').location
$E = (Invoke-RestMethod -Method Post "$base/locations" -ContentType "application/json" -Body '{"code":"E","name":"Customer E","kind":"CUSTOMER","x":900,"y":500}').location

# 2. Load Worked Example Roads
$roads = @(
    @{ from_id = $D.id; to_id =$A.id; distance_km = 4.0;  is_one_way = $false; is_closed =$false },
    @{ from_id = $D.id; to_id =$B.id; distance_km = 2.0;  is_one_way = $false; is_closed =$false },
    @{ from_id = $B.id; to_id =$A.id; distance_km = 1.0;  is_one_way = $false; is_closed =$false },
    @{ from_id = $A.id; to_id =$C.id; distance_km = 5.0;  is_one_way = $false; is_closed =$false },
    @{ from_id = $B.id; to_id =$C.id; distance_km = 9.0;  is_one_way = $false; is_closed =$false },
    @{ from_id = $B.id; to_id =$E.id; distance_km = 10.0; is_one_way = $false; is_closed =$false },
    @{ from_id = $C.id; to_id =$E.id; distance_km = 2.0;  is_one_way = $false; is_closed =$false }
)
$createdRoads = @{}
foreach ($r in $roads) {$res = (Invoke-RestMethod -Method Post "$base/roads" -ContentType "application/json" -Body ($r | ConvertTo-Json)).road
    $createdRoads["$($r.from_id)-$($r.to_id)"] = $res
}

# 3. Compute Shortest Path D -> E (Expected: 10.0 km via D -> B -> A -> C -> E)
$route10 = (Invoke-RestMethod -Method Post "$base/routes/point" -ContentType "application/json" -Body (@{
    origin_id = $D.id; destination_id = $E.id; avg_speed_kmh = 40.0; save =$true
} | ConvertTo-Json)).route
Write-Host "10 km Route (D -> B -> A -> C -> E): $($route10.total_km) km | Path IDs: $($route10.path -join ' -> ')"

# 4. Close Road A-C
$acRoadId =$createdRoads["$($A.id)-$($C.id)"].id
Invoke-RestMethod -Method Patch "$base/roads/$acRoadId" -ContentType "application/json" -Body '{"is_closed": true}' | Out-Null

# 5. Recompute Shortest Path D -> E (Expected: 12.0 km detour via D -> B -> E)
$route12 = (Invoke-RestMethod -Method Post "$base/routes/point" -ContentType "application/json" -Body (@{
    origin_id = $D.id; destination_id = $E.id; avg_speed_kmh = 40.0; save =$true
} | ConvertTo-Json)).route
Write-Host "12 km Detour (D -> B -> E): $($route12.total_km) km | Path IDs: $($route12.path -join ' -> ')"
```

*(Optionally, open the frontend UI while the temporary server is running to inspect the saved `10.0 km` and `12.0 km` routes in **Route History**, or stop the server with `Ctrl + C` and restart Step 1 to verify persistence across restarts).*

### Step 3: Clean Up Temporary Database
After stopping the temporary server (`Ctrl + C`), delete the temporary SQLite file:

```powershell
Remove-Item cp2_demo_temp.db -ErrorAction SilentlyContinue
```