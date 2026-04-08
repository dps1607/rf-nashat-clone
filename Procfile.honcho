rag: gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5051 --chdir rag_server app:app
admin: gunicorn --workers 2 --bind 0.0.0.0:$PORT --chdir admin_ui app:app
