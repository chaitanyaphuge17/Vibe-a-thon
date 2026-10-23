from contextlib import asynccontextmanager
import asyncio
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import ApiError, router
from app.tick import run_tick


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    async def tick_loop() -> None:
        while True:
            run_tick()
            await asyncio.sleep(1)

    tick_task = asyncio.create_task(tick_loop())
    try:
        yield
    finally:
        tick_task.cancel()
        try:
            await tick_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="FreshRelay API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
def handle_request_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "The request body does not match the expected shape.",
            }
        },
    )


app.include_router(router)
