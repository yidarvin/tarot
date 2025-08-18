### tarot
Do a tarot reading.

### Prerequisites
- **Python**: 3.11+
- **Docker**: 24+ and **Docker Compose** (v2)

### Configuration (.env)
Create a `.env` file at the project root (next to `app.py`). At minimum set where to save Markdown readings:

```
PATH_TO_SAVE=/absolute/path/on/your/machine/obsidian/Tarot

# Optional: enable AI interpretations
OPENAI_API_KEY=sk-...

# Optional: host port to expose Flask (default 5000)
PORT=5000
```

### Run locally with a virtual environment
1) Create and activate a venv, then install deps:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Ensure `.env` contains `PATH_TO_SAVE` (and optionally `OPENAI_API_KEY`). The app and CLI auto-load `.env` via `python-dotenv`.

3) Run the CLI (`spread.py`):
```
python spread.py 3card --seed 42 --no-interpret
python spread.py celticcross --reversal-prob 0.4
```
This writes Markdown files to `PATH_TO_SAVE`.

4) Run the web app (`app.py`):
```
python app.py
```
Visit `http://localhost:5000` and click a spread, e.g. `http://localhost:5000/spread/3card`.

### Run with Docker & Docker Compose
This repo includes a `Dockerfile` and `docker-compose.yml` to run `app.py` and persist saved readings.

#### Mounting PATH_TO_SAVE (host) into the container
Set `PATH_TO_SAVE` in your root `.env` to an absolute host path. The compose file maps that to `/data/saves` in the container, and the app uses `PATH_TO_SAVE=/data/saves` internally.

Example `.env`:
```
PATH_TO_SAVE=/Users/you/Documents/Obsidian/Tarot
OPENAI_API_KEY=sk-...   # optional
PORT=5000               # optional
```

The relevant portion of `docker-compose.yml` is:
```
environment:
  - PORT=5000
  - PATH_TO_SAVE=/data/saves
  - OPENAI_API_KEY=${OPENAI_API_KEY}
volumes:
  - ${PATH_TO_SAVE:-/tmp/tarot_saves}:/data/saves
ports:
  - "${PORT:-5000}:5000"
```

#### Build and run the web app via Compose
```
docker compose build
docker compose up
```
Then open `http://localhost:5000`.

#### Run the CLI via Compose (using the same image)
You can execute `spread.py` inside the built container, still saving to your host path via the mounted volume:
```
docker compose run --rm app python spread.py 3card --seed 123 --no-interpret
docker compose run --rm app python spread.py celticcross --reversal-prob 0.4
```

### Notes
- If `OPENAI_API_KEY` is not set, interpretations and summaries will be skipped gracefully; card draws and Markdown saving still work.
- Card images are bundled under `cards/standard` and are served by the Flask route `/cards/<filename>`.
