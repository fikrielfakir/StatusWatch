-- Optimized PostgreSQL Database Schema for DownDetector Clone
-- Date: 2025-01-03
-- Optimizations: Better data types, proper constraints, timestamps, indexes

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS user_favorites CASCADE;
DROP TABLE IF EXISTS service_channels CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS outage_reports CASCADE;
DROP TABLE IF EXISTS services CASCADE;
DROP TABLE IF EXISTS service_subtypes CASCADE;
DROP TABLE IF EXISTS service_types CASCADE;
DROP TABLE IF EXISTS notification_channels CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create Users table with authentication support
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create Service Types table
CREATE TABLE service_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    icon_class VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Service Subtypes table
CREATE TABLE service_subtypes (
    id SERIAL PRIMARY KEY,
    type_id INTEGER NOT NULL REFERENCES service_types(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(type_id, name)
);

-- Create Notification Channels table
CREATE TABLE notification_channels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL, -- email, sms, webhook, push
    configuration JSONB, -- Store channel-specific config
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Services table (optimized)
CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    type_id INTEGER NOT NULL REFERENCES service_types(id) ON DELETE RESTRICT,
    subtype_id INTEGER REFERENCES service_subtypes(id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    url VARCHAR(500),
    company VARCHAR(100),
    logo_url VARCHAR(500),
    icon_path VARCHAR(255),
    current_status VARCHAR(20) DEFAULT 'up', -- up, issues, down
    last_checked TIMESTAMP WITH TIME ZONE,
    response_time INTEGER, -- in milliseconds
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 1, -- 1=low, 2=medium, 3=high
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Outage Reports table (optimized from Down table)
CREATE TABLE outage_reports (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    type VARCHAR(50) DEFAULT 'user_report', -- user_report, automatic, webhook
    title VARCHAR(200),
    description TEXT,
    country VARCHAR(100),
    region VARCHAR(100),
    city VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    user_ip INET,
    user_agent TEXT,
    source VARCHAR(100),
    severity VARCHAR(20) DEFAULT 'medium', -- low, medium, high, critical
    status VARCHAR(20) DEFAULT 'open', -- open, investigating, resolved, closed
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Comments table (optimized)
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_id INTEGER REFERENCES services(id) ON DELETE CASCADE,
    report_id INTEGER REFERENCES outage_reports(id) ON DELETE CASCADE,
    parent_comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    likes_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (service_id IS NOT NULL OR report_id IS NOT NULL)
);

-- Create User Favorites table (optimized from Favorite table)
CREATE TABLE user_favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    notification_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, service_id)
);

-- Create Service Channels relationship table (optimized from choseChannel)
CREATE TABLE service_channels (
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    configuration JSONB, -- Channel-specific settings for this service
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (service_id, channel_id)
);

-- Create indexes for better performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_services_name ON services(name);
CREATE INDEX idx_services_type_id ON services(type_id);
CREATE INDEX idx_services_status ON services(current_status);
CREATE INDEX idx_services_company ON services(company);
CREATE INDEX idx_outage_reports_service_id ON outage_reports(service_id);
CREATE INDEX idx_outage_reports_user_id ON outage_reports(user_id);
CREATE INDEX idx_outage_reports_created_at ON outage_reports(created_at DESC);
CREATE INDEX idx_outage_reports_location ON outage_reports(country, region, city);
CREATE INDEX idx_outage_reports_status ON outage_reports(status);
CREATE INDEX idx_comments_service_id ON comments(service_id);
CREATE INDEX idx_comments_report_id ON comments(report_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE INDEX idx_comments_created_at ON comments(created_at DESC);
CREATE INDEX idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX idx_user_favorites_service_id ON user_favorites(service_id);

-- Create triggers for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables with updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_service_types_updated_at BEFORE UPDATE ON service_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_service_subtypes_updated_at BEFORE UPDATE ON service_subtypes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_notification_channels_updated_at BEFORE UPDATE ON notification_channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_services_updated_at BEFORE UPDATE ON services
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_outage_reports_updated_at BEFORE UPDATE ON outage_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_comments_updated_at BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Insert default data
INSERT INTO service_types (name, description, icon_class) VALUES
('Social Media', 'Social networking and communication platforms', 'fas fa-users'),
('Email & Communication', 'Email services and messaging platforms', 'fas fa-envelope'),
('Entertainment', 'Streaming and entertainment services', 'fas fa-play'),
('Cloud Services', 'Cloud computing and storage services', 'fas fa-cloud'),
('E-commerce', 'Online shopping and marketplace platforms', 'fas fa-shopping-cart'),
('Gaming', 'Gaming platforms and services', 'fas fa-gamepad'),
('News & Media', 'News and media websites', 'fas fa-newspaper'),
('Finance', 'Banking and financial services', 'fas fa-dollar-sign'),
('Education', 'Educational platforms and services', 'fas fa-graduation-cap'),
('Other', 'Other services not categorized above', 'fas fa-globe');

-- Insert default notification channels
INSERT INTO notification_channels (name, type, configuration) VALUES
('Email Notifications', 'email', '{"smtp_server": "localhost", "port": 587}'),
('SMS Alerts', 'sms', '{"provider": "twilio"}'),
('Webhook Notifications', 'webhook', '{"timeout": 30}'),
('Push Notifications', 'push', '{"service": "firebase"}');