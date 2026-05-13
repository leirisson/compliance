from db.session import init_db, engine
from sqlalchemy import text

init_db()
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ))
    print("Tabelas criadas:", [r[0] for r in rows])
