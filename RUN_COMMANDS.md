# Run Commands

## Option A: Local Run (Windows PowerShell)

### 1) Go to project root
cd D:\Nance

### 2) Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

### 3) Install dependencies
pip install -r requirements.txt

### 4) Create environment file
Copy-Item .env.example .env

### 5) Start PostgreSQL and Redis
Use local services if already installed, or run with Docker:

docker run --name peer-postgres -e POSTGRES_DB=peer_platform -e POSTGRES_USER=peer_user -e POSTGRES_PASSWORD=peer_pass -p 5432:5432 -d postgres:16

docker run --name peer-redis -p 6379:6379 -d redis:7

### 6) Run Django migrations
cd .\src
python manage.py migrate

### 7) Create admin user
python manage.py createsuperuser

### 8) Start Django app
python manage.py runserver

### 9) Start Celery worker (new terminal)
cd D:\Nance\src
..\.venv\Scripts\Activate.ps1
celery -A config worker --loglevel=INFO

### 10) Start Celery beat (new terminal)
cd D:\Nance\src
..\.venv\Scripts\Activate.ps1
celery -A config beat --loglevel=INFO

### 11) Open app
Frontend login:
http://127.0.0.1:8000/app/login/

Django admin:
http://127.0.0.1:8000/admin/


## Option B: Full Docker Run

### 1) Go to project root
cd D:\Nance

### 2) Create environment file
Copy-Item .env.example .env

### 3) Start all services
docker compose up --build

### 4) Open app
Frontend login:
http://127.0.0.1:8000/app/login/

Django admin:
http://127.0.0.1:8000/admin/


## Useful Commands

### Run tests
cd D:\Nance\src
python manage.py test --settings=config.settings.test

### Django system check
cd D:\Nance\src
python manage.py check

### Create new migrations
cd D:\Nance\src
python manage.py makemigrations

### Apply migrations
cd D:\Nance\src
python manage.py migrate

### Stop Docker stack
cd D:\Nance
docker compose down
