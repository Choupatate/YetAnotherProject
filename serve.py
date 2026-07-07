import os

from waitress import serve

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5011))
    serve(app, host="0.0.0.0", port=port)
