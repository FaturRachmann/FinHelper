from fastapi import Depends, Request
from app.services.gsheets_service import GoogleSheetsService

def get_sheets_service(request: Request) -> GoogleSheetsService:
    """Dependency to get the Google Sheets service from app state"""
    return request.app.state.sheets_service