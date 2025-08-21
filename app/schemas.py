from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

# Enums
class AccountTypeSchema(str, Enum):
    BANK = "bank"
    E_WALLET = "e_wallet"
    CASH = "cash"
    CREDIT_CARD = "credit_card"

class TransactionTypeSchema(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

class TransactionSourceSchema(str, Enum):
    MANUAL = "manual"
    CSV_IMPORT = "csv_import"
    TELEGRAM_BOT = "telegram_bot"

# Base schemas
class AccountBase(BaseModel):
    name: str = Field(..., max_length=100)
    account_type: AccountTypeSchema
    currency: str = Field(default="IDR", max_length=3)
    balance: Optional[float] = 0.0

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    balance: Optional[float] = None
    is_active: Optional[bool] = None

class Account(BaseModel):
    id: int
    name: str
    account_type: str
    currency: Optional[str] = None        # allow None
    balance: float
    is_active: bool
    created_at: Optional[datetime] = None # allow None

    class Config:
        from_attributes = True

# Category schemas
class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=7, pattern="^#[0-9A-Fa-f]{6}$")

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=7, pattern="^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None

class Category(CategoryBase):
    id: int
    is_active: bool
    
    class Config:
        from_attributes = True

# Transaction schemas
class TransactionBase(BaseModel):
    timestamp: datetime
    account_id: int
    amount: float = Field(..., gt=0)
    transaction_type: TransactionTypeSchema
    category_id: Optional[int] = None
    merchant: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    source: TransactionSourceSchema = TransactionSourceSchema.MANUAL

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    timestamp: Optional[datetime] = None
    amount: Optional[float] = Field(None, gt=0)
    transaction_type: Optional[TransactionTypeSchema] = None
    category_id: Optional[int] = None
    merchant: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

class Transaction(TransactionBase):
    id: int
    reference_id: Optional[str]
    is_synced_to_sheets: bool
    created_at: datetime
    account: Optional[Account] = None
    category: Optional[Category] = None
    
    class Config:
        from_attributes = True

# Budget schemas
class BudgetBase(BaseModel):
    category_id: int
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")  # YYYY-MM format
    amount_limit: float = Field(..., gt=0)
    alert_threshold: float = Field(default=0.8, ge=0.1, le=1.0)

class BudgetCreate(BudgetBase):
    pass

class BudgetUpdate(BaseModel):
    amount_limit: Optional[float] = Field(None, gt=0)
    alert_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)
    is_active: Optional[bool] = None

class Budget(BudgetBase):
    id: int
    amount_spent: float
    is_active: bool
    created_at: datetime
    category: Optional[Category] = None
    
    @validator('amount_spent')
    def calculate_spent_percentage(cls, v, values):
        if 'amount_limit' in values:
            return round((v / values['amount_limit']) * 100, 2)
        return 0
    
    class Config:
        from_attributes = True

# Dashboard schemas
class DashboardSummary(BaseModel):
    total_balance: float
    monthly_income: float
    monthly_expenses: float
    monthly_savings: float
    account_balances: List[dict]
    expense_by_category: List[dict]
    daily_flow: List[dict]  # Tambahkan field ini
    recent_transactions: List[Transaction]

class MonthlyReport(BaseModel):
    month: str
    income: float
    expenses: float
    savings: float
    top_categories: List[dict]
    daily_flow: List[dict]

# Response schemas
class ResponseModel(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

# Telegram Bot schemas
class TelegramTransaction(BaseModel):
    amount: float
    merchant: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None