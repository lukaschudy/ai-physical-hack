"""HTTP API. All routes under /api; the Vite dev server proxies /api here."""

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from .config import load_settings
from .deps import build_pipeline
from .models import AnswerResult, BatchResult, CreateSessionRequest, Session
from .pipeline import Conflict, NotFound, Pipeline, Upstream

BATCH_SIZE = 10


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    pipe = pipeline or build_pipeline(load_settings())
    app = FastAPI(title="AI Physical Hack")

    async def call(fn, *args):
        """Run a blocking pipeline step off the event loop and map its errors to HTTP."""
        try:
            return await run_in_threadpool(fn, *args)
        except NotFound as e:
            raise HTTPException(404, f"not found: {e}") from e
        except Conflict as e:
            raise HTTPException(409, str(e)) from e
        except Upstream as e:
            raise HTTPException(502, str(e)) from e

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/sessions")
    def create_session(req: CreateSessionRequest) -> Session:
        return pipe.start(req.task)

    @app.get("/api/sessions")
    def list_sessions() -> list[Session]:
        return pipe.sessions.list()

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> Session:
        session = pipe.sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "session not found")
        return session

    @app.post("/api/sessions/{session_id}/batches")
    async def post_batch(
        session_id: str,
        images: list[UploadFile] = File(...),
        captured_at_s: float | None = Form(None, ge=0, allow_inf_nan=False),
    ) -> BatchResult:
        if len(images) != BATCH_SIZE:
            raise HTTPException(422, f"expected {BATCH_SIZE} images, got {len(images)}")
        if bad := [f.filename for f in images if not (f.content_type or "").startswith("image/")]:
            raise HTTPException(415, f"not an image: {', '.join(map(str, bad))}")
        data = [await f.read() for f in images]
        if empty := [f.filename for f, d in zip(images, data, strict=True) if not d]:
            raise HTTPException(422, f"empty image: {', '.join(map(str, empty))}")
        batch = await call(pipe.process_batch, session_id, data, captured_at_s)
        url = (
            f"/api/sessions/{session_id}/questions/{batch.question.id}/audio"
            if batch.question
            else None
        )
        return BatchResult(batch=batch, question_audio_url=url)

    @app.get("/api/sessions/{session_id}/questions/{question_id}/audio")
    async def question_audio(session_id: str, question_id: str) -> Response:
        audio, mime = await call(pipe.question_audio, session_id, question_id)
        return Response(audio, media_type=mime)

    @app.post("/api/sessions/{session_id}/answers")
    async def post_answer(
        session_id: str, question_id: str = Form(..., min_length=1), audio: UploadFile = File(...)
    ) -> AnswerResult:
        data = await audio.read()
        if not data:
            raise HTTPException(422, "empty audio")
        mime = audio.content_type or "application/octet-stream"
        return AnswerResult(answer=await call(pipe.answer, session_id, question_id, data, mime))

    @app.post("/api/sessions/{session_id}/finish")
    async def finish(session_id: str) -> Session:
        return await call(pipe.finish, session_id)

    @app.get("/api/files/{rel:path}")
    def file(rel: str) -> FileResponse:
        try:
            path = pipe.blobs.path(rel)
        except ValueError as e:
            raise HTTPException(400, "bad path") from e
        if not path.is_file():
            raise HTTPException(404, "file not found")
        return FileResponse(path)

    return app


app = create_app()
