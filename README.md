# Bus2Hike
Unibz epic project.

`docker compose up -d` to start containers

Here is our plan to do this:

# Hiking Route Planner with Public Transport - Architecture & Implementation Guide

## Executive Summary

**Recommended Stack:**
- **Backend**: Python (Flask/FastAPI)
- **Frontend**: React with Leaflet
- **Database**: PostgreSQL with PostGIS
- **Routing**: Custom Python routing logic (no OTP needed for this scope)
- **Timeline**: 7 days feasible with this architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Leaflet)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Map Display  │  │ Trail Search │  │ Route Itinerary    │   │
│  │ (Leaflet)    │  │ & Filters    │  │ Display            │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP REST API
┌────────────────────────────▼────────────────────────────────────┐
│              Backend API (Python Flask/FastAPI)                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Route Planning Service                                   │  │
│  │  - Find nearest stops to trailhead                        │  │
│  │  - Calculate PT routes (Dijkstra's algorithm)            │  │
│  │  - Estimate hiking duration                               │  │
│  │  - Suggest return trip times                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Services                                            │  │
│  │  - OpenDataHub integration                                │  │
│  │  - NeTEx parser (STA data)                                │  │
│  │  - PostGIS spatial queries                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              PostgreSQL + PostGIS Database                       │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ hiking_trails │  │ pt_stops     │  │ pt_routes        │    │
│  │ (geometry)    │  │ (geometry)   │  │ (schedules)      │    │
│  └───────────────┘  └──────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack (Detailed)

### Backend: Python
**Framework**: FastAPI (recommended) or Flask
- **FastAPI**: Modern, fast, automatic API docs, async support
- **Flask**: Simpler, more resources available for learning

**Key Libraries**:
```python
# Core
fastapi==0.104.1          # Web framework
uvicorn==0.24.0           # ASGI server
pydantic==2.5.0           # Data validation

# Database & Geospatial
psycopg2-binary==2.9.9    # PostgreSQL driver
geoalchemy2==0.14.2       # Spatial ORM
sqlalchemy==2.0.23        # ORM
shapely==2.0.2            # Geometry operations

# Data Processing
requests==2.31.0          # HTTP client for ODH API
lxml==4.9.3               # XML parsing (NeTEx)
pandas==2.1.3             # Data manipulation
numpy==1.26.2             # Numerical operations

# Routing
networkx==3.2.1           # Graph algorithms for PT routing
```

### Frontend: React
**Core Stack**:
```json
{
  "react": "^18.2.0",
  "leaflet": "^1.9.4",
  "react-leaflet": "^4.2.1",
  "axios": "^1.6.0",
  "tailwindcss": "^3.3.5"
}
```

### Database: PostgreSQL + PostGIS
- **PostgreSQL 15+**: Reliable, open-source
- **PostGIS 3.4+**: Spatial extensions for geographic queries

## Project Structure

```
hiking-transport-planner/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI app entry
│   │   ├── config.py                    # Configuration
│   │   ├── database.py                  # DB connection
│   │   │
│   │   ├── models/                      # Database models
│   │   │   ├── __init__.py
│   │   │   ├── trail.py
│   │   │   ├── pt_stop.py
│   │   │   └── pt_route.py
│   │   │
│   │   ├── schemas/                     # Pydantic schemas (API contracts)
│   │   │   ├── __init__.py
│   │   │   ├── trail.py
│   │   │   ├── route_request.py
│   │   │   └── route_response.py
│   │   │
│   │   ├── services/                    # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── odh_service.py          # Fetch hiking trails from ODH
│   │   │   ├── netex_parser.py         # Parse STA NeTEx data
│   │   │   ├── routing_service.py       # PT routing algorithm
│   │   │   ├── trail_service.py         # Trail queries & filtering
│   │   │   └── spatial_service.py       # PostGIS spatial queries
│   │   │
│   │   ├── routers/                     # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── trails.py               # GET /api/trails
│   │   │   ├── routes.py               # POST /api/plan-route
│   │   │   └── stops.py                # GET /api/stops
│   │   │
│   │   └── utils/                       # Utilities
│   │       ├── __init__.py
│   │       ├── geom_utils.py           # Geometry helpers
│   │       └── time_utils.py           # Time calculations
│   │
│   ├── scripts/                         # One-time setup scripts
│   │   ├── init_db.py                  # Create tables
│   │   ├── import_trails.py            # Load ODH data
│   │   └── import_netex.py             # Load STA PT data
│   │
│   ├── tests/
│   │   ├── test_routing.py
│   │   └── test_trails.py
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   │   ├── MapView.jsx
│   │   │   │   ├── TrailLayer.jsx
│   │   │   │   └── RouteLayer.jsx
│   │   │   ├── TrailSearch/
│   │   │   │   ├── SearchBar.jsx
│   │   │   │   ├── FilterPanel.jsx
│   │   │   │   └── TrailList.jsx
│   │   │   ├── RoutePlanner/
│   │   │   │   ├── StartPointSelector.jsx
│   │   │   │   ├── TimeSelector.jsx
│   │   │   │   └── ItineraryDisplay.jsx
│   │   │   └── shared/
│   │   │       ├── Button.jsx
│   │   │       └── LoadingSpinner.jsx
│   │   ├── services/
│   │   │   ├── api.js                  # Axios API client
│   │   │   └── mapUtils.js
│   │   ├── hooks/
│   │   │   ├── useTrails.js
│   │   │   └── useRoutePlanning.js
│   │   ├── App.jsx
│   │   ├── index.js
│   │   └── index.css
│   ├── package.json
│   └── tailwind.config.js
│
├── database/
│   ├── schema.sql                       # Database schema
│   └── seed_data.sql                    # Sample data (optional)
│
├── docker-compose.yml                   # PostgreSQL + PostGIS
├── .gitignore
└── README.md
```

## Database Schema

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;

-- Hiking Trails
CREATE TABLE hiking_trails (
    id SERIAL PRIMARY KEY,
    odh_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    name_de VARCHAR(500),
    name_it VARCHAR(500),
    name_en VARCHAR(500),
    difficulty VARCHAR(50),              -- easy, intermediate, difficult
    length_km DECIMAL(10, 2),
    duration_minutes INTEGER,            -- estimated hiking time
    elevation_gain_m INTEGER,
    elevation_loss_m INTEGER,
    description TEXT,
    geometry GEOMETRY(LineString, 4326), -- trail path
    start_point GEOMETRY(Point, 4326),   -- trailhead
    end_point GEOMETRY(Point, 4326),     -- trail end
    circular BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Spatial index for faster queries
CREATE INDEX idx_trails_geometry ON hiking_trails USING GIST(geometry);
CREATE INDEX idx_trails_start_point ON hiking_trails USING GIST(start_point);
CREATE INDEX idx_trails_end_point ON hiking_trails USING GIST(end_point);
CREATE INDEX idx_trails_difficulty ON hiking_trails(difficulty);

-- Public Transport Stops
CREATE TABLE pt_stops (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(255) UNIQUE NOT NULL, -- from NeTEx
    name VARCHAR(500) NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    stop_type VARCHAR(50),               -- bus, train, etc.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stops_location ON pt_stops USING GIST(location);
CREATE INDEX idx_stops_stop_id ON pt_stops(stop_id);

-- Public Transport Routes
CREATE TABLE pt_routes (
    id SERIAL PRIMARY KEY,
    route_id VARCHAR(255) NOT NULL,
    route_name VARCHAR(500),
    transport_mode VARCHAR(50),          -- bus, train
    created_at TIMESTAMP DEFAULT NOW()
);

-- Stop Times (schedule)
CREATE TABLE stop_times (
    id SERIAL PRIMARY KEY,
    route_id INTEGER REFERENCES pt_routes(id),
    stop_id INTEGER REFERENCES pt_stops(id),
    arrival_time TIME NOT NULL,
    departure_time TIME NOT NULL,
    stop_sequence INTEGER NOT NULL,
    day_of_week INTEGER[],               -- [1,2,3,4,5] for Mon-Fri
    valid_from DATE,
    valid_until DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stop_times_route ON stop_times(route_id);
CREATE INDEX idx_stop_times_stop ON stop_times(stop_id);
CREATE INDEX idx_stop_times_departure ON stop_times(departure_time);

-- Route Connections (for graph-based routing)
CREATE TABLE route_connections (
    id SERIAL PRIMARY KEY,
    from_stop_id INTEGER REFERENCES pt_stops(id),
    to_stop_id INTEGER REFERENCES pt_stops(id),
    route_id INTEGER REFERENCES pt_routes(id),
    travel_time_minutes INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_connections_from_stop ON route_connections(from_stop_id);
CREATE INDEX idx_connections_to_stop ON route_connections(to_stop_id);
```

## Implementation Phases (7-Day Timeline)

### Day 1: Setup & Data Import
**Goals**: Environment setup, database, import initial data

**Tasks**:
1. Set up PostgreSQL + PostGIS (use Docker)
2. Create database schema
3. Set up Python backend skeleton (FastAPI)
4. Write NeTEx parser script
5. Import STA public transport data
6. Write ODH API integration script
7. Import hiking trails from OpenDataHub

**Deliverables**:
- Working database with trails and PT data
- Backend can query trails via API

### Day 2: Backend Core Services
**Goals**: Implement spatial queries and basic routing

**Tasks**:
1. Implement trail search/filter service
2. Implement spatial queries (find nearest stops to point)
3. Build PT graph from stop_times and connections
4. Implement basic routing algorithm (Dijkstra)
5. Create API endpoints for trails and stops

**Deliverables**:
- API endpoints: `GET /api/trails`, `GET /api/stops/nearest`
- Working spatial queries

### Day 3: Route Planning Logic
**Goals**: Complete routing algorithm with schedules

**Tasks**:
1. Implement time-dependent routing (considering schedules)
2. Calculate hiking duration estimates
3. Suggest return trip times
4. Implement route planning endpoint
5. Add total journey time calculation

**Deliverables**:
- API endpoint: `POST /api/plan-route`
- Working end-to-end route calculation

### Day 4: Frontend Setup & Map
**Goals**: React app with interactive map

**Tasks**:
1. Initialize React project
2. Set up Leaflet map component
3. Display hiking trails on map
4. Implement trail selection (click or search)
5. Display PT stops on map

**Deliverables**:
- Interactive map showing trails
- Basic UI for trail selection

### Day 5: Frontend Route Planning UI
**Goals**: Complete user interface for planning

**Tasks**:
1. Starting point selector (map click, GPS, stop selection)
2. Trail search and filter panel
3. Time availability input
4. Connect frontend to backend API
5. Display route results

**Deliverables**:
- Complete UI for route planning
- Display planned routes on map

### Day 6: Itinerary Display & Polish
**Goals**: Show detailed step-by-step itinerary

**Tasks**:
1. Itinerary component with PT steps
2. Show departure/arrival times
3. Display hiking portion
4. Return trip information
5. Error handling and loading states

**Deliverables**:
- Complete itinerary view
- Polished user experience

### Day 7: Testing & Documentation
**Goals**: Bug fixes, testing, documentation

**Tasks**:
1. End-to-end testing with real scenarios
2. Fix critical bugs
3. Write README documentation
4. Prepare deployment instructions
5. Final polish and optimization

**Deliverables**:
- Working application
- Documentation

## Key Algorithms

### 1. Finding Nearest PT Stops to Trailhead

```python
# Using PostGIS spatial query
def find_nearest_stops(trailhead_point, max_distance_km=2, limit=5):
    """
    Find PT stops within walking distance of trailhead
    """
    query = """
    SELECT 
        id, 
        stop_id, 
        name,
        ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) as distance_m
    FROM pt_stops
    WHERE ST_DWithin(
        location::geography,
        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
        %s
    )
    ORDER BY distance_m
    LIMIT %s
    """
    # Execute with lon, lat, max_distance_m
```

### 2. Public Transport Routing

Use **Dijkstra's algorithm** with time constraints:

```python
import networkx as nx
from datetime import datetime, timedelta

def build_pt_graph(departure_time, day_of_week):
    """
    Build directed graph of PT network for given time
    """
    G = nx.DiGraph()
    
    # Add edges for all valid connections at this time
    connections = get_valid_connections(departure_time, day_of_week)
    
    for conn in connections:
        G.add_edge(
            conn['from_stop'],
            conn['to_stop'],
            weight=conn['travel_time'],
            route_id=conn['route_id'],
            departure=conn['departure_time'],
            arrival=conn['arrival_time']
        )
    
    return G

def find_pt_route(start_stop, end_stop, departure_time):
    """
    Find shortest PT route considering schedules
    """
    day_of_week = departure_time.weekday()
    G = build_pt_graph(departure_time, day_of_week)
    
    try:
        path = nx.shortest_path(G, start_stop, end_stop, weight='weight')
        # Extract detailed itinerary from path
        return build_itinerary(G, path)
    except nx.NetworkXNoPath:
        return None
```

### 3. Hiking Duration Estimation

```python
def estimate_hiking_time(trail):
    """
    Estimate hiking time based on Naismith's rule + adjustments
    
    Naismith's rule: 
    - 5 km/h on flat terrain
    - +1 hour per 600m elevation gain
    - -10 minutes per 300m descent (less significant)
    """
    base_time = (trail.length_km / 5.0) * 60  # minutes
    
    # Add time for elevation gain
    climb_time = (trail.elevation_gain_m / 600.0) * 60
    
    # Subtract time for descent (optional, smaller factor)
    descent_time = (trail.elevation_loss_m / 300.0) * 10
    
    # Difficulty adjustment
    difficulty_multipliers = {
        'easy': 1.0,
        'intermediate': 1.2,
        'difficult': 1.5
    }
    multiplier = difficulty_multipliers.get(trail.difficulty, 1.0)
    
    total_time = (base_time + climb_time - descent_time) * multiplier
    
    # Add buffer for breaks (10%)
    return int(total_time * 1.1)
```

## API Endpoints

### GET /api/trails
Get all trails with optional filters
```json
Query params:
- difficulty: easy|intermediate|difficult
- min_length: float (km)
- max_length: float (km)
- max_duration: int (minutes)
- bbox: comma-separated coordinates (for map bounds)

Response:
{
  "trails": [
    {
      "id": 1,
      "name": "Rosengarten Trail",
      "difficulty": "intermediate",
      "length_km": 12.5,
      "duration_minutes": 300,
      "elevation_gain_m": 850,
      "start_point": {"lat": 46.4, "lon": 11.6},
      "geometry": {...}
    }
  ]
}
```

### GET /api/trails/{trail_id}
Get detailed trail information

### POST /api/plan-route
Plan complete journey with PT
```json
Request:
{
  "start_location": {
    "type": "coordinates|stop_id",
    "value": {"lat": 46.4, "lon": 11.6} // or stop_id
  },
  "trail_id": 1,
  "departure_time": "2025-01-15T09:00:00",
  "available_time_minutes": 480  // 8 hours total
}

Response:
{
  "feasible": true,
  "total_duration_minutes": 450,
  "outbound_journey": {
    "departure_time": "09:00:00",
    "arrival_time": "10:15:00",
    "steps": [
      {
        "type": "walk",
        "from": "Start Location",
        "to": "Bus Stop Bolzano Centro",
        "duration_minutes": 5
      },
      {
        "type": "bus",
        "route": "Line 10A",
        "from": "Bolzano Centro",
        "to": "Ponte Nova",
        "departure": "09:10:00",
        "arrival": "10:05:00",
        "stops": 12
      },
      {
        "type": "walk",
        "from": "Ponte Nova",
        "to": "Trailhead",
        "duration_minutes": 10
      }
    ]
  },
  "hiking": {
    "trail_name": "Rosengarten Trail",
    "start_time": "10:15:00",
    "estimated_end_time": "15:15:00",
    "duration_minutes": 300,
    "distance_km": 12.5
  },
  "return_journey": {
    "departure_time": "15:30:00",
    "arrival_time": "16:45:00",
    "steps": [...]
  }
}
```

### GET /api/stops/nearest
Find nearest PT stops to a location
```json
Query params:
- lat: float
- lon: float
- max_distance_m: int (default 2000)
- limit: int (default 5)
```

## NeTEx Data Parsing

The STA provides NeTEx XML files. You'll need to parse these:

```python
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import requests

def download_and_parse_netex(url):
    """
    Download NeTEx ZIP, extract and parse XML
    """
    # Download ZIP
    response = requests.get(url)
    
    with ZipFile(BytesIO(response.content)) as zip_file:
        for filename in zip_file.namelist():
            if filename.endswith('.xml'):
                with zip_file.open(filename) as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Parse namespaces
                    ns = {
                        'netex': 'http://www.netex.org.uk/netex',
                        'gml': 'http://www.opengis.net/gml/3.2'
                    }
                    
                    # Extract stops
                    stops = parse_stops(root, ns)
                    
                    # Extract routes and schedules
                    routes = parse_routes(root, ns)
                    
                    return stops, routes

def parse_stops(root, ns):
    """
    Extract stop information from NeTEx
    """
    stops = []
    
    for stop_place in root.findall('.//netex:StopPlace', ns):
        stop_id = stop_place.get('id')
        name = stop_place.find('.//netex:Name', ns).text
        
        # Get coordinates
        pos = stop_place.find('.//gml:pos', ns)
        if pos is not None:
            coords = pos.text.split()
            lat, lon = float(coords[0]), float(coords[1])
            
            stops.append({
                'stop_id': stop_id,
                'name': name,
                'lat': lat,
                'lon': lon
            })
    
    return stops

# Similar parsing for routes, schedules, etc.
```

## Frontend React Components

### Main App Structure

```jsx
// App.jsx
import React, { useState } from 'react';
import MapView from './components/Map/MapView';
import TrailSearch from './components/TrailSearch/SearchBar';
import RoutePlanner from './components/RoutePlanner/RoutePlanner';
import ItineraryDisplay from './components/RoutePlanner/ItineraryDisplay';

function App() {
  const [selectedTrail, setSelectedTrail] = useState(null);
  const [startLocation, setStartLocation] = useState(null);
  const [plannedRoute, setPlannedRoute] = useState(null);

  return (
    <div className="flex h-screen">
      {/* Left Sidebar */}
      <div className="w-96 bg-white shadow-lg overflow-y-auto">
        <div className="p-4">
          <h1 className="text-2xl font-bold mb-4">
            Hiking Route Planner
          </h1>
          
          <TrailSearch 
            onTrailSelect={setSelectedTrail}
            selectedTrail={selectedTrail}
          />
          
          {selectedTrail && (
            <RoutePlanner
              trail={selectedTrail}
              startLocation={startLocation}
              onStartLocationChange={setStartLocation}
              onRouteCalculated={setPlannedRoute}
            />
          )}
          
          {plannedRoute && (
            <ItineraryDisplay route={plannedRoute} />
          )}
        </div>
      </div>
      
      {/* Map */}
      <div className="flex-1">
        <MapView
          trails={trails}
          selectedTrail={selectedTrail}
          onTrailClick={setSelectedTrail}
          startLocation={startLocation}
          onMapClick={setStartLocation}
          plannedRoute={plannedRoute}
        />
      </div>
    </div>
  );
}
```

## Deployment (Local Machine)

### Using Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgis/postgis:15-3.4
    environment:
      POSTGRES_USER: hikingapp
      POSTGRES_PASSWORD: hikingpass
      POSTGRES_DB: hiking_planner
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://hikingapp:hikingpass@db:5432/hiking_planner
    depends_on:
      - db
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm start

volumes:
  postgres_data:
```

### Running the Application

```bash
# Start all services
docker-compose up -d

# Import data (first time only)
docker-compose exec backend python scripts/import_trails.py
docker-compose exec backend python scripts/import_netex.py

# Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Challenges & Solutions

### Challenge 1: NeTEx Complexity
**Problem**: NeTEx XML is complex and verbose
**Solution**: Focus on essential elements (stops, routes, stop_times). Create a simplified import script that extracts only what you need.

### Challenge 2: PT Routing Performance
**Problem**: Graph-based routing can be slow with many stops
**Solution**: 
- Pre-compute route_connections table
- Limit search radius from trailheads
- Cache common routes

### Challenge 3: Schedule Coordination
**Problem**: Return trip timing must account for hiking duration
**Solution**: 
- Calculate hiking time estimate
- Find next available PT departure after estimated finish
- Show multiple return options

### Challenge 4: Circular vs Linear Trails
**Problem**: Circular trails end where they start; linear trails need different PT stops
**Solution**:
- Store `circular` boolean in database
- For circular: use same stop for outbound/return
- For linear: find nearest stops to both start and end points

## Testing Strategy

### Unit Tests
```python
# tests/test_routing.py
def test_find_nearest_stops():
    """Test spatial query for nearest stops"""
    point = (11.3547, 46.4983)  # Bolzano coordinates
    stops = find_nearest_stops(point, max_distance_km=1)
    assert len(stops) > 0
    assert all(stop['distance_m'] <= 1000 for stop in stops)

def test_estimate_hiking_time():
    """Test hiking duration calculation"""
    trail = Trail(
        length_km=10,
        elevation_gain_m=600,
        elevation_loss_m=300,
        difficulty='intermediate'
    )
    duration = estimate_hiking_time(trail)
    assert 200 < duration < 400  # Reasonable range
```

### Integration Tests
- Test complete route planning flow
- Test with real trail and stop data
- Verify API responses

### Manual Testing Scenarios
1. Plan route from Bolzano center to popular trail
2. Filter trails by difficulty and duration
3. Test with limited available time
4. Test circular vs linear trails
5. Test edge cases (no PT connection available)

## Performance Optimization

1. **Database Indexing**: Already included in schema
2. **API Caching**: Cache trail data (changes infrequently)
3. **Frontend Optimization**: Virtualize long trail lists
4. **Map Performance**: Cluster markers when zoomed out
5. **Route Calculation**: Limit graph search depth/time

## Future Enhancements (Post-MVP)

1. Real-time PT data integration
2. Weather information
3. Trail conditions/closures
4. User accounts and saved routes
5. Mobile app version
6. Multi-day hiking trips
7. Accommodation suggestions
8. Share routes with others

## Summary

This architecture provides:
- ✅ Simple monolithic approach (easier for 3 people in 7 days)
- ✅ Python backend (as requested)
- ✅ Modern React frontend
- ✅ PostGIS for spatial operations
- ✅ Custom routing (no complex OTP setup)
- ✅ Zero-cost deployment (self-hosted)
- ✅ Realistic 7-day timeline

The key to success: **Focus on core functionality first**. Get basic route planning working, then add polish and features as time permits.
