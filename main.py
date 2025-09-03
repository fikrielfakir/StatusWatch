from app import app

# This is the WSGI app for gunicorn
application = app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
