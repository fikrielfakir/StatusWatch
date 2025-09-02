# Overview

DownDetector Clone is a full-stack web application for monitoring service outages and status reporting. Users can view service statuses on a dashboard, report outages for specific services, and administrators can manage services through an admin panel. The application provides real-time updates, interactive maps for report locations, and data visualizations for trending outage reports.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture

**Flask Web Framework**: Uses Flask as the core web framework with modular blueprint structure separating authentication (`auth.py`), main routes (`routes.py`), and application initialization (`app.py`).

**Database Layer**: 
- SQLAlchemy ORM with SQLite database for lightweight deployment
- Three main models: User (authentication), Service (monitored services), Report (outage reports)
- Automatic database initialization with default admin user creation

**Real-time Communication**: 
- Flask-SocketIO integration for WebSocket support
- Eventlet async server for handling concurrent connections
- Live status updates pushed to connected clients

**Authentication System**:
- Flask-Login for session management
- Password hashing with Werkzeug security utilities
- Role-based access control (admin vs regular users)

## Frontend Architecture

**Template Engine**: Jinja2 templating with base template inheritance for consistent UI structure

**Responsive Design**: Bootstrap CSS framework with dark theme for mobile-friendly interface

**Interactive Components**:
- Chart.js for data visualization and trending graphs
- Leaflet.js for interactive maps showing report locations
- Feather Icons for consistent iconography

**Client-side JavaScript**: Vanilla JavaScript modules for each page (dashboard.js, service-detail.js, admin.js) handling dynamic interactions and API communication

## Data Models

**Service Model**: Stores monitored services with status calculation logic based on recent reports
**Report Model**: Tracks outage reports with timestamps, locations, and descriptions
**User Model**: Handles authentication with admin role capabilities

## API Design

RESTful API endpoints for:
- Service management (GET/POST `/api/services`)
- Report submission and retrieval
- Real-time status updates via WebSocket events

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web application framework
- **Flask-SocketIO**: WebSocket support for real-time features
- **Flask-Login**: User session management
- **Flask-SQLAlchemy**: Database ORM layer
- **Eventlet**: Async server support
- **Gunicorn**: Production WSGI server

## Frontend Libraries (CDN)
- **Bootstrap CSS**: UI framework with dark theme
- **Chart.js**: Data visualization library
- **Leaflet.js**: Interactive mapping library
- **Socket.IO Client**: WebSocket client library
- **Feather Icons**: Icon library

## Database
- **SQLite**: Lightweight file-based database for development and small-scale deployment

## Development Tools
- **Werkzeug**: Security utilities for password hashing
- **ProxyFix**: Middleware for handling proxy headers in production

The application is designed to run on Replit with minimal configuration, using environment variables for database connection and session secrets. The architecture supports easy scaling by switching from SQLite to PostgreSQL via the DATABASE_URL environment variable.