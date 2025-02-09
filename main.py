"""This module create an instance of the Flask application using
the factory function and starts the Flask application server."""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
