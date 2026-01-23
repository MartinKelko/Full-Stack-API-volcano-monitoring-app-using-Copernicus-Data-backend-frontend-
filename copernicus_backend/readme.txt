SPUSTANIE BACKENDU cez batch file
C:\Users\kelko_m\Geospatial\API_proj\copernicus_backend\run_report.bat
----------------
SPUSTANIE BACKENDU cez WINDOWS POWERSHELL
pustat z rootu (C:\Users\kelko_m\Geospatial\API_proj\copernicus_backend\)

Backend reload
.\.venv\Scripts\python -m uvicorn app.main:app --reload

run_job
.\.venv\Scripts\python scripts\run_job.py
----------------
KONFIGURACIA v PYCHARM
-.env_job
tu sa nastavuje date range a cloud coverage
-run_job.py
na riadku 20 (# nastavenie date range (taktiez aj v env_job)) sa nastavuje date range a cloud coverage
na riadku 125 (compose email) sa nastavuju premenne v texte emailu
-aois.json
tu sa pridava bbox. copernicus browser a tam zakreslit map extent a skopirovat suradnice a vlozit podla vzoru v json
-.env
nastavenie client ID, client secret, token Url a Base Url
----------------
POSTMAN
tu sa testuju volania
GET latest scene a GET process staci prepisat nazov vulkanu ako je v url http://127.0.0.1:8000/aois/kilauea/latest-fc (staci zmenit nazov vulkanu)
