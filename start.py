
from app import app as app

if __name__ == '__main__':
    app.run(
        host='127.0.0.1',
        port=5000,
        threaded=True,
        ssl_context=None
    )
