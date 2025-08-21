from fastapi import APIRouter, Depends, HTTPException, Query, Body, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import asyncio
import inspect

from app.models import get_db, Transaction, Account, Category
from app.schemas import (
    TransactionCreate, TransactionUpdate, Transaction as TransactionSchema,
    ResponseModel
)
from app.services.gsheets_service import GoogleSheetsService
from app.services.categorizer import AutoCategorizer

# Tambahkan import ini di bagian atas file
from app.dependencies import get_sheets_service

router = APIRouter()

# Initialize services
gsheets_service = GoogleSheetsService()
categorizer = AutoCategorizer()

@router.post("/", response_model=ResponseModel)
async def create_transaction(
    transaction: TransactionCreate = Body(...),
    sync_to_sheets: bool = Query(True),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    import logging
    try:
        account = db.get(Account, transaction.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")

        model_cols = {c.name for c in Transaction.__table__.columns}
        kwargs = {}
        for col in model_cols:
            if col in ("id", "created_at"):
                continue
            if hasattr(transaction, col):
                kwargs[col] = getattr(transaction, col)

        if "date" in model_cols and "date" not in kwargs:
            ts = getattr(transaction, "timestamp", None) or getattr(transaction, "date", None)
            if ts is not None:
                try:
                    kwargs["date"] = ts.date().isoformat()
                except Exception:
                    s = str(ts)
                    kwargs["date"] = s.split("T")[0] if "T" in s else s

        TRANSACTION_TYPE_MAP = {"income": "INCOME", "expense": "EXPENSE", "transfer": "TRANSFER"}
        SOURCE_MAP = {
            "manual": "MANUAL",
            "csv_import": "CSV_IMPORT",
            "csv-import": "CSV_IMPORT",
            "csv": "CSV_IMPORT",
            "telegram_bot": "TELEGRAM_BOT",
            "telegram": "TELEGRAM_BOT",
        }

        if "transaction_type" in kwargs and isinstance(kwargs["transaction_type"], str):
            v = kwargs["transaction_type"].strip()
            kwargs["transaction_type"] = TRANSACTION_TYPE_MAP.get(v.lower(), v.upper())

        if "source" in kwargs and isinstance(kwargs["source"], str):
            v = kwargs["source"].strip().lower().replace(" ", "_")
            kwargs["source"] = SOURCE_MAP.get(v, v.upper())

        # Auto-categorize if no category provided
        provided_category_id = kwargs.get("category_id")
        if not provided_category_id:
            try:
                inferred_category_id = await categorizer.categorize_transaction(
                    merchant=kwargs.get("merchant"),
                    description=kwargs.get("description"),
                    amount=kwargs.get("amount", 0) or 0,
                    db=db,
                )
                if inferred_category_id:
                    kwargs["category_id"] = inferred_category_id
            except Exception:
                logging.exception("Auto-categorization failed; proceeding without category")

        tx = Transaction(**kwargs)
        db.add(tx)
        db.commit()
        db.refresh(tx)

        if sync_to_sheets:
            try:
                svc = GoogleSheetsService()
                if getattr(svc, "client", None):
                    if background_tasks is not None:
                        background_tasks.add_task(svc.add_transaction, tx)
                    else:
                        try:
                            svc.add_transaction(tx)
                        except Exception:
                            logging.exception("Non-fatal: failed to sync to Google Sheets (sync fallback)")
                else:
                    logging.warning("GoogleSheetsService not initialized: %s", getattr(svc, "init_error", None))
            except Exception:
                logging.exception("Non-fatal: failed to schedule sync to Google Sheets")

        # Pydantic v2: validate ORM object to schema then dump to dict for ResponseModel
        tx_data = TransactionSchema.model_validate(tx, from_attributes=True).model_dump()
        return ResponseModel(success=True, data=tx_data, message="Created")
    except HTTPException:
        # biarkan HTTPException diteruskan (mis. 404 Account not found)
        raise
    except Exception:
        logging.exception("Failed creating transaction")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[TransactionSchema])
async def get_transactions(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    account_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None)
):
    """Get transactions with optional filters"""
    query = db.query(Transaction)
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    if start_date:
        query = query.filter(Transaction.timestamp >= start_date)
    if end_date:
        query = query.filter(Transaction.timestamp <= end_date)
    
    transactions = query.order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
    return transactions

@router.get("/{transaction_id}", response_model=TransactionSchema)
async def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get specific transaction"""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@router.put("/{transaction_id}", response_model=ResponseModel)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Update a transaction"""
    try:
        db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not db_transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Store old amount for balance calculation
        old_amount = db_transaction.amount
        old_type = db_transaction.transaction_type
        
        # Update transaction fields
        update_data = transaction_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_transaction, field, value)
        
        # Update account balance if amount or type changed
        if 'amount' in update_data or 'transaction_type' in update_data:
            account = db.query(Account).filter(Account.id == db_transaction.account_id).first()
            
            # Reverse old transaction effect
            if old_type.value == "income":
                account.balance -= old_amount
            elif old_type.value == "expense":
                account.balance += old_amount
            
            # Apply new transaction effect
            if db_transaction.transaction_type.value == "income":
                account.balance += db_transaction.amount
            elif db_transaction.transaction_type.value == "expense":
                account.balance -= db_transaction.amount
        
        # Mark as not synced to sheets
        db_transaction.is_synced_to_sheets = False
        
        db.commit()
        
        return ResponseModel(
            success=True,
            message="Transaction updated successfully"
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{transaction_id}", response_model=ResponseModel)
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Delete a transaction"""
    try:
        db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not db_transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Update account balance
        account = db.query(Account).filter(Account.id == db_transaction.account_id).first()
        if db_transaction.transaction_type.value == "income":
            account.balance -= db_transaction.amount
        elif db_transaction.transaction_type.value == "expense":
            account.balance += db_transaction.amount
        
        db.delete(db_transaction)
        db.commit()
        
        return ResponseModel(
            success=True,
            message="Transaction deleted successfully"
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-to-sheets", response_model=ResponseModel)
async def sync_transactions_to_sheets(
    db: Session = Depends(get_db),
    force_all: bool = Query(default=False),
    sheets_service: GoogleSheetsService = Depends(get_sheets_service)
):
    """Sync unsynced transactions to Google Sheets"""
    try:
        # Verifikasi service terinisialisasi dengan benar
        if not sheets_service or not sheets_service.client:
            return ResponseModel(
                success=False,
                message="Google Sheets service not initialized. Check your credentials.",
                data={"error": str(getattr(sheets_service, "init_error", "Unknown error"))}
            )
            
        query = db.query(Transaction)
        if not force_all:
            query = query.filter(Transaction.is_synced_to_sheets == False)
        
        transactions = query.all()
        
        synced_count = 0
        failed_count = 0
        errors = []
        
        for transaction in transactions:
            try:
                await sheets_service.add_transaction(transaction)
                transaction.is_synced_to_sheets = True
                synced_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({"id": transaction.id, "error": str(e)})
                print(f"Failed to sync transaction {transaction.id}: {e}")
        
        db.commit()
        
        return ResponseModel(
            success=synced_count > 0,
            message=f"Synced {synced_count} transactions to Google Sheets. Failed: {failed_count}.",
            data={
                "synced_count": synced_count,
                "failed_count": failed_count,
                "errors": errors[:5]  # Batasi jumlah error yang ditampilkan
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/monthly")
async def get_monthly_analytics(
    db: Session = Depends(get_db),
    year: int = Query(default=None),
    month: int = Query(default=None)
):
    """Get monthly transaction analytics"""
    if not year or not month:
        now = datetime.now()
        year, month = now.year, now.month
    
    # Calculate date range
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    transactions = db.query(Transaction).filter(
        Transaction.timestamp >= start_date,
        Transaction.timestamp < end_date
    ).all()
    
    # Calculate analytics
    income = sum(t.amount for t in transactions if t.transaction_type.value == "income")
    expenses = sum(t.amount for t in transactions if t.transaction_type.value == "expense")
    
    # Group by category
    category_expenses = {}
    for t in transactions:
        if t.transaction_type.value == "expense" and t.category:
            cat_name = t.category.name
            category_expenses[cat_name] = category_expenses.get(cat_name, 0) + t.amount
    
    return {
        "month": f"{year}-{month:02d}",
        "income": income,
        "expenses": expenses,
        "savings": income - expenses,
        "category_breakdown": category_expenses,
        "transaction_count": len(transactions)
    }