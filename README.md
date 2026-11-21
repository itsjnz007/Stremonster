# Stremonster
Stremio web scraper addon.

Python version 3.13

## Run

Install the Python dependencies and the UI dependencies once:

```sh
pip install -r requirements.txt
cd app/ui
npm ci
cd ../..
python run.py
```

Starting `run.py` builds the UI and serves it at `http://localhost:8000/`. The
existing Stremio addon and streaming endpoints remain available on the same
server.
