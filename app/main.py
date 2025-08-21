from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from pathlib import Path

from app.api import transactions, budgets, reports
from app.models import Base, engine, get_db
from app.services.gsheets_service import GoogleSheetsService

# Initialize templates
templates = Jinja2Templates(directory="templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    print("Database tables created")
    
    # Initialize Google Sheets service once at startup
    sheets_service = GoogleSheetsService()
    success = await sheets_service.initialize()
    if success:
        app.state.sheets_service = sheets_service
        print("Google Sheets service initialized successfully")
    else:
        print("WARNING: Google Sheets service initialization failed")
        app.state.sheets_service = None
        
    yield
    # Shutdown
    print("Shutting down...")

# FastAPI app instance
app = FastAPI(
    title="FinHelper - Personal Finance Assistant",
    description="Track your finances with Google Sheets integration",
    version="1.0.0",
    lifespan=lifespan
)

# resolve static dir relatif ke project root (dua level dari this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"

# pastikan mount hanya sekali, gunakan path absolut untuk keandalan
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# jika template masih memanggil /js/... Anda bisa juga mount /js ke static/js
app.mount("/js", StaticFiles(directory=str(STATIC_DIR / "js")), name="js")

# Include API routers
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

# Dashboard route
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/transactions", response_class=HTMLResponse)
async def transactions_page(request: Request):
    """Transactions management page"""
    return templates.TemplateResponse("transactions.html", {"request": request})

@app.get("/budgets", response_class=HTMLResponse)
async def budgets_page(request: Request):
    """Budget management page"""
    return templates.TemplateResponse("budgets.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)