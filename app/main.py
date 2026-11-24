import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
from .storage import Store, Conflict
from .web import secure
from .domain import analyze, validate_mapping, export_csv
from .schema import FIELDS

ROOT = Path(__file__).resolve().parents[1]


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv: str = Field(min_length=1, max_length=256000)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    mapping: dict[str, str | None] = Field(max_length=32)


def create_app(path=None):
    load_dotenv(ROOT / ".env")
    store = Store(path or os.getenv("DATABASE_PATH", str(ROOT / "data/schemabridge.sqlite")))
    app = FastAPI(title="SchemaBridge", version="1.0.0")
    secure(app)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Run not found"}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/schema")
    def schema():
        return FIELDS

    @app.get("/api/sample")
    def sample():
        return {"csv": (ROOT / "samples/customers.csv").read_text()}

    @app.get("/api/runs")
    def runs():
        return store.list()

    @app.post("/api/runs", status_code=201)
    def create(body: ImportRequest):
        return store.create(analyze(body.csv))

    @app.get("/api/runs/{rid}")
    def get(rid: str):
        return store.get(rid)

    @app.post("/api/runs/{rid}/review")
    def review(rid: str, body: Review):
        return store.update(rid, body.version, lambda p: validate_mapping(p, body.mapping))

    @app.get("/api/runs/{rid}/export")
    def export(rid: str):
        return Response(
            export_csv(store.get(rid)),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="validated-customers.csv"'},
        )

    @app.get("/")
    def home():
        return FileResponse(ROOT / "static/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
