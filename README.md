# Etzan - Backend API

## Project Overview
Etzan (House of Life) is an AI-driven platform for psychological, neurological, astrological, and letter science analysis. The backend provides robust RESTful APIs for user management, comprehensive assessments, payment processing via Fawaterk, and an integrated administrative dashboard.

## Technical Stack
- Framework: FastAPI (Python 3.11+)
- Database: PostgreSQL (SQLAlchemy AsyncPG)
- Authentication: JWT, bcrypt
- AI Integrations: OpenAI API
- Push Notifications: Firebase Cloud Messaging (FCM)
- Containerization: Docker & Docker Compose

## Prerequisites
- Docker and Docker Compose (Recommended)
- Python 3.11+ (If running locally without Docker)
- PostgreSQL database
- Valid API keys (OpenAI, Fawaterk, Firebase Admin SDK JSON)

## Running the Application

### 1. Environment Configuration
Create a `.env` file in the root directory. At a minimum, you need the following variables:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/baytalhayat

# Security
SECRET_KEY=your_secure_random_string
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# External Integrations
OPENAI_API_KEY=sk-...
FAWATERK_API_KEY=...
FAWATERK_MODE=test
```

### 2. Starting with Docker (Production/Staging)
The application is fully containerized. To build and start the server:

```bash
docker-compose up -d --build
```
This will start the FastAPI application on port 8000. To view the logs:
```bash
docker-compose logs -f web
```

### 3. Starting Locally (Development)
If you prefer running the application without Docker during development:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Project Architecture & Structure
The codebase follows a modular design pattern to separate concerns between routing, business logic, and database operations.

- `main.py`
  The main entry point. Initializes the FastAPI instance, configures CORS, handles application lifespan (database initialization), and includes all routers.

- `app/database.py`
  Configures the SQLAlchemy asynchronous engine and connection pool. Contains `init_db` which automatically creates tables and seeds default assessment questions on startup.

- `app/models/`
  Contains all SQLAlchemy ORM models representing the database schema (e.g., users, payments, subscriptions, settings).

- `app/schemas/`
  Contains Pydantic models used for API request validation and response formatting.

- `app/routes/`
  Contains the API endpoints. Segmented by feature (e.g., `admin.py`, `payment.py`, `psychology.py`, `notification.py`).

- `app/services/`
  Contains the heavy lifting and business logic. External API calls (OpenAI), complex data manipulation, and scoring algorithms are placed here to keep the route files clean.

- `app/auth/`
  Handles authentication logic, JWT token generation/validation, and subscription enforcement middlewares.

## Important Notes for Maintainers

1. API Documentation: Swagger UI (/docs) is disabled when deployed using the provided docker-compose configuration for security purposes. To enable it locally, remove the `ENABLE_DOCS=false` environment variable.
   
2. Default Questions: Psychology and Neuroscience questions are dynamically seeded into the database upon startup. Do not hardcode questions into the service files.
   
3. Background Tasks: Email sending and certain heavy operations utilize FastAPI's native BackgroundTasks to prevent blocking API responses.
   
4. Code Cleanliness: The codebase has been stripped of emojis and localized Arabic comments to maintain standard UTF-8 encoding compliance and readability for non-Arabic speaking backend developers. Ensure all new logs and code comments remain in English.
