# Bus2Hike
An epic project made at the University of Bolzano.

### Authors
Alessandro Fantesini<br>
Antonia Stieger<br>
Ondrej Mueller

## How to start the application
Clone this repository<br>
Create .env file with this template:

```
# PostgreSQL
POSTGRES_DB=db
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_OUT_PORT=5432

# Backend
DATABASE_URL=postgresql+psycopg2://user:password@postgres:5432/db

# Chat GPT
OPEN_AI_API_KEY=<your open api key>
```

`docker compose up -d --build`

# Generate Trails

`docker exec <container-name> python app/find_trails.py --lat --long --distance --max-length --max-trails` to generate GEOjson trails data to standard output.

# Import script: `import_odh.py`
`docker exec -it <container-name> python scripts/<script-name>.py <transport_stops_limit> <trails_limit>`
For full import of trails and transport stops don't pass  <transport_stops_limit> <trails_limit> and leave it empty.
`docker exec -it <container-name> python scripts/<script-name>.py`

# To use scripts
`docker exec -it <container-name> python scripts/<script-name>.py`
# To use the test scripts
`docker exec -it <container-name> python -m pytest tests/<script-name>.py`

Here is our plan to do this:

# Hiking Route Planner with Public Transport - Architecture & Implementation Guide

## Executive Summary

**Recommended Stack:**
- **Backend**: Python (Flask/FastAPI)
- **Frontend**: React with Leaflet
- **Database**: PostgreSQL with PostGIS
- **Routing**: Custom Python routing logic (no OTP needed 

