from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from db.session import init_db
from api.routes import router

app = FastAPI(
    title="Compliance Manaus",
    description="POC — Consulta de conformidade regulatória (IPAAM/AM)",
    version="0.1.0",
    default_response_class=ORJSONResponse,
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
