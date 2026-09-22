RENDER DEPLOYMENT

1. Upload/push the CONTENTS of this folder to the ROOT of your GitHub repository.
   The root must directly contain app.py and requirements.txt.

2. The root must also contain:
   templates/base.html
   templates/landing.html
   templates/login.html
   templates/register.html
   templates/dashboard.html
   templates/management.html
   static/style.css

3. On Render, use:
   Environment: Python
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn --bind 0.0.0.0:$PORT app:app

4. Add an environment variable:
   SECRET_KEY = a-long-random-secret

5. Deploy/redeploy. Test:
   /health   -> should show OK
   /         -> should show the application landing page

IMPORTANT:
Do NOT upload the old ecell_terminal.db. The application creates its SQLite
file automatically in Flask's writable instance directory. SQLite data on
Render is ephemeral unless you attach persistent storage or move to Postgres.

If Render still returns a Flask 500 after this package is deployed, open
Render -> Service -> Logs and use the traceback immediately above the 500.
That traceback identifies the exact application error.
