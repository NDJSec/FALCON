src/
 ├── pyproject.toml
 └── app/
     ├── core/
     │    ├── __init__.py
     │    ├── config.py
     │    ├── db.py
     │    ├── logger.py
     │    └── schemas.py
     │
     ├── backend/         # API + DB + MCP
     │    ├── __init__.py
     │    ├── main.py
     │    ├── db_logger.py
     │    ├── mcp_client_sync.py
     │    ├── models/
     │    │    └── __init__.py
     │    ├── routes/
     │    │    ├── __init__.py
     │    │    └── users.py
     │    └── services/
     │         ├── __init__.py
     │         └── user_service.py
     │
     └── frontend/        # UI / Web app
          ├── __init__.py
          ├── ui.py       # FastAPI app serving templates
          ├── templates/
          │    └── index.html
          └── static/
               └── style.css
