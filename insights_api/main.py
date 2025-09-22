from fastapi import FastAPI
from insights_routes import insights_router


app = FastAPI(
    title="Insights API",
    summary="API for handling insights",
)


app.include_router(insights_router)