# Bus2Hike
An epic project made at the University of Bolzano.

So, you are a poor student not having a car and looking for some bus stops:
![Bus stops](/assets/bus-stops.png)

Now imagine that:
 - you can select a stop
 - search for hikes within 1km of that stop

After you click the button with the beautiful blue color you'll see hikes:

![Hikes](/assets/hikes.png)

You're starting to get it because now:
- you can choose a hike
- get informed
- start your adventure


### Authors
Alessandro Fantesini<br>
Antonia Stieger<br>
Ondrej Mueller

## How to start the application
### Prerequisites
- laptop
- brain
- love hikes
- iOS
- docker & python

### Instructions
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

Start up the containers:
`docker compose up -d --build`

Yeah, Docker Compose (or chatGPT?) received some update so you don't have to use --env-file .env anymore.

#### Where is frontend?
Hehehe, hope you have a Mac.

On Mac please do this:
1. Download XCode
2. Open the .xcodeproj in /bus2hike_app
3. Choose a run destination (simulator) or connect a physical ipad with cable
4. Click play button and see the magic happen

## Import data

Import with this scrip: `import_odh.py`

#### Usage
- If you want to limit data: <br>
`docker exec -it <container-name> python scripts/<script-name>.py <transport_stops_limit> <trails_limit>`

- If you don't want to limit data import of trails and transport stops don't pass <transport_stops_limit> <trails_limit> and leave it empty: <br>
`docker exec -it <container-name> python scripts/<script-name>.py`

## Generate Trails

`docker exec <container-name> python app/find_trails.py --lat --long --distance --max-length --max-trails` to generate GEOjson trails data to standard output.


## To use the test scripts
`docker exec -it <container-name> python -m pytest tests/<script-name>.py`

# Architecture

- **Backend**: Python - FastAPI
- **Frontend**: Swift
- **Database**: PostgreSQL with PostGIS

## Here is a pretty C4 container diagram of our app

<img src="assets/container-diagram.png" alt="Container diagram" style="background-color: white;" />


## This is how we got the data for oup app

<img src="assets/data-pipeline.png" alt="Data pipeline" style="background-color: white;" />