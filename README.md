# Student Job Tracker (FastAPI + SQLite + HTMX)

This is a lightweight web app for tracking student jobs, payment status, and outstanding fees.

## What you need on Linux Mint

1. Python 3.10 or newer.
2. `pip` (Python package installer).
3. A terminal.

## 1) Get the project

If you already have the project folder, open a terminal in that folder.

If not, clone it first:

```bash
git clone <your-repo-url>
cd All-Statistic-python-work
```

## 2) Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should now see `(.venv)` at the start of your terminal line.

## 3) Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Start the app

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 5) Open in browser

Go to:

```text
http://127.0.0.1:8000
```

You will see:
- Top analytics cards (active jobs, cash collected, debt owed)
- Quick Add form
- Job table

## 6) How to use the app

1. Add a new job from the Quick Add form.
2. Click **Status** in a row to cycle: `Pending -> In Progress -> Completed`.
3. Click **Priority** in a row to cycle: `Low -> Medium -> High`.
4. Edit **Fee Paid** and click **Save** to update payment.
5. Click **Delete** to remove a job.

Changes update instantly without full page reload (HTMX behavior).

## Data file location

SQLite database file is created automatically as:

```text
student_jobs.db
```

It is saved in the project root folder.

## Stop the app

Press:

```text
Ctrl + C
```

## Run again later

From the project folder:

```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Common issues (Linux Mint)

### `python3: command not found`
Install Python:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

### Port 8000 already in use
Run on another port:

```bash
uvicorn main:app --host 0.0.0.0 --port 8010
```

Then open `http://127.0.0.1:8010`.

### You want auto-reload while developing

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
