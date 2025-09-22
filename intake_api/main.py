from fastapi import FastAPI
from lead_routes import leads_router


app = FastAPI(
    title="Leads API",
    summary="API for handling leads",
)


app.include_router(leads_router)