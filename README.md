# DownDetector Clone

A full-stack web application similar to DownDetector for monitoring service outages and status, built with Flask backend and responsive HTML/JavaScript frontend.

## Features

- **Real-time Service Monitoring**: Track the status of various online services
- **Outage Reporting**: Users can report service outages with location and description
- **Interactive Dashboard**: View all services with status indicators (green/yellow/red)
- **Service Detail Pages**: Detailed view with charts, maps, and reporting forms
- **Admin Dashboard**: Manage services and view all reports
- **Real-time Updates**: WebSocket integration for live status updates
- **Responsive Design**: Mobile-friendly interface using Bootstrap
- **Interactive Maps**: Leaflet.js integration for displaying report locations
- **Charts & Analytics**: Chart.js for visualizing report trends

## Tech Stack

### Backend
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket support for real-time updates
- **Flask-Login**: User authentication
- **Flask-SQLAlchemy**: Database ORM
- **SQLite**: Lightweight database
- **Eventlet**: Async server support

### Frontend
- **HTML5**: Semantic markup
- **Bootstrap CSS**: Responsive styling with dark theme
- **Vanilla JavaScript**: Client-side functionality
- **Chart.js**: Data visualization
- **Leaflet.js**: Interactive maps
- **Socket.IO Client**: Real-time communication
- **Feather Icons**: Beautiful icons

## Installation & Setup

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd downdetector-clone
   ```

2. **Install dependencies**
   ```bash
   pip install flask flask-socketio flask-login flask-sqlalchemy eventlet requests gunicorn
   ```

3. **Set environment variables**
   ```bash
   export SESSION_SECRET="your-secret-key-here"
   export DATABASE_URL="sqlite:///downdetector.db"
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

5. **Access the application**
   - Open your browser to `http://localhost:5000`
   - Default admin credentials: `admin` / `admin123`

### Replit Deployment

1. **Upload files to Replit**
   - Create a new Python Repl
   - Upload all project files

2. **Install dependencies**
   - Replit will automatically detect and install dependencies

3. **Set environment secrets**
   - Go to the "Secrets" tab in Replit
   - Add `SESSION_SECRET` with a secure random string

4. **Run the application**
   - Click the "Run" button
   - The application will be available at your Replit URL

## Usage

### For Regular Users

1. **View Service Status**
   - Visit the main dashboard to see all monitored services
   - Green = Operational, Yellow = Some Issues, Red = Service Down

2. **Report Issues**
   - Click on any service to go to its detail page
   - Click "Report Problem" to submit an outage report
   - Optionally share your location for map visualization

3. **View Analytics**
   - See real-time charts showing report trends
   - View report locations on interactive maps

### For Administrators

1. **Login**
   - Click "Admin Login" in the navigation
   - Use credentials: `admin` / `admin123`

2. **Manage Services**
   - Add new services to monitor
   - Edit existing service details
   - Remove services (this deletes all associated reports)

3. **Monitor Reports**
   - View all recent reports across all services
   - Access detailed analytics and trends

## API Endpoints

- `GET /api/services` - List all services with status
- `POST /api/services` - Add new service (admin only)
- `GET /api/reports/<service_id>` - Get reports for a service
- `POST /api/report` - Submit new outage report
- `GET /api/chart-data/<service_id>` - Get chart data for service

## Configuration

### Environment Variables

- `SESSION_SECRET`: Secret key for session management
- `DATABASE_URL`: Database connection string (defaults to SQLite)

### Default Services

The application comes pre-configured with popular services:
- WhatsApp
- Instagram
- Facebook
- Twitter
- YouTube
- Gmail
- Discord
- TikTok

## Architecture

### Database Schema

**Services Table**
- id (Primary Key)
- name (Service name)
- url (Service URL)
- created_at (Timestamp)

**Reports Table**
- id (Primary Key)
- service_id (Foreign Key)
- timestamp (Report time)
- location (User location)
- description (Issue description)
- latitude/longitude (GPS coordinates)
- user_ip (For spam prevention)

**Users Table**
- id (Primary Key)
- username (Unique)
- email (Unique)
- password_hash (Hashed password)
- is_admin (Admin flag)

### Status Detection Algorithm

Services are automatically marked based on report frequency:
- **Operational (Green)**: < 2 reports in last hour
- **Some Issues (Yellow)**: 2-4 reports in last hour
- **Service Down (Red)**: 5+ reports in last hour

## Security Features

- Password hashing using Werkzeug
- CSRF protection via Flask-WTF
- Input validation and sanitization
- Rate limiting for report submissions (max 3 per 5 minutes per IP)
- SQL injection prevention via SQLAlchemy ORM

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue in the repository or contact the development team.
