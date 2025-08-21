from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timedelta
import calendar

from app.models import get_db, Transaction, Account, Category, Budget
from app.schemas import DashboardSummary, MonthlyReport, ResponseModel
from app.services.gsheets_service import GoogleSheetsService

router = APIRouter()
gsheets_service = GoogleSheetsService()

@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary data"""
    try:
        # Calculate current month dates
        now = datetime.now()
        start_of_month = datetime(now.year, now.month, 1)
        if now.month == 12:
            end_of_month = datetime(now.year + 1, 1, 1)
        else:
            end_of_month = datetime(now.year, now.month + 1, 1)
        
        # Get total balance from all accounts
        accounts = db.query(Account).filter(Account.is_active == True).all()
        total_balance = sum(account.balance for account in accounts)
        
        # Account balances
        account_balances = [
            {"name": account.name, "balance": account.balance, "type": account.account_type.value}
            for account in accounts
        ]
        
        # Monthly transactions
        monthly_transactions = db.query(Transaction).filter(
            Transaction.timestamp >= start_of_month,
            Transaction.timestamp < end_of_month
        ).all()
        
        # Calculate monthly totals
        monthly_income = sum(t.amount for t in monthly_transactions if t.transaction_type.value == "income")
        monthly_expenses = sum(t.amount for t in monthly_transactions if t.transaction_type.value == "expense")
        monthly_savings = monthly_income - monthly_expenses
        
        # Expense by category
        expense_by_category = []
        category_expenses = {}
        
        for transaction in monthly_transactions:
            if transaction.transaction_type.value == "expense":
                if transaction.category:
                    cat_name = transaction.category.name
                else:
                    cat_name = "Uncategorized"
                category_expenses[cat_name] = category_expenses.get(cat_name, 0) + transaction.amount
        
        expense_by_category = [
            {"category": category, "amount": amount}
            for category, amount in sorted(category_expenses.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Daily flow for the past 30 days
        daily_flow = []
        for i in range(30):
            date = (now - timedelta(days=29-i)).date()
            day_start = datetime.combine(date, datetime.min.time())
            day_end = datetime.combine(date, datetime.max.time())
            
            day_transactions = []
            for t in monthly_transactions:
                if day_start <= t.timestamp <= day_end:
                    day_transactions.append(t)
            
            day_income = sum(t.amount for t in day_transactions if t.transaction_type.value == "income")
            day_expenses = sum(t.amount for t in day_transactions if t.transaction_type.value == "expense")
            
            daily_flow.append({
                "date": date.isoformat(),
                "income": day_income,
                "expenses": day_expenses
            })
        
        # Recent transactions
        recent_transactions = db.query(Transaction).order_by(
            Transaction.timestamp.desc()
        ).limit(5).all()
        
        return DashboardSummary(
            total_balance=total_balance,
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            monthly_savings=monthly_savings,
            account_balances=account_balances,
            expense_by_category=expense_by_category,
            daily_flow=daily_flow,
            recent_transactions=recent_transactions
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monthly/{year}/{month}", response_model=MonthlyReport)
async def get_monthly_report(
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """Get detailed monthly report"""
    try:
        # Validate month
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="Invalid month")
        
        # Calculate date range
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get transactions for the month
        transactions = db.query(Transaction).filter(
            Transaction.timestamp >= start_date,
            Transaction.timestamp < end_date
        ).all()
        
        # Calculate totals
        income = sum(t.amount for t in transactions if t.transaction_type.value == "income")
        expenses = sum(t.amount for t in transactions if t.transaction_type.value == "expense")
        savings = income - expenses
        
        # Top categories
        category_totals = {}
        for transaction in transactions:
            if transaction.category:
                cat_name = transaction.category.name
                if cat_name not in category_totals:
                    category_totals[cat_name] = {"income": 0, "expenses": 0}
                
                if transaction.transaction_type.value == "income":
                    category_totals[cat_name]["income"] += transaction.amount
                else:
                    category_totals[cat_name]["expenses"] += transaction.amount
        
        top_categories = []
        for category, amounts in category_totals.items():
            total_amount = amounts["expenses"] + amounts["income"]
            top_categories.append({
                "category": category,
                "income": amounts["income"],
                "expenses": amounts["expenses"],
                "total": total_amount
            })
        
        top_categories.sort(key=lambda x: x["total"], reverse=True)
        top_categories = top_categories[:10]
        
        # Daily flow
        daily_flow = []
        days_in_month = calendar.monthrange(year, month)[1]
        
        for day in range(1, days_in_month + 1):
            day_date = datetime(year, month, day)
            day_transactions = [t for t in transactions 
                             if t.timestamp.date() == day_date.date()]
            
            day_income = sum(t.amount for t in day_transactions if t.transaction_type.value == "income")
            day_expenses = sum(t.amount for t in day_transactions if t.transaction_type.value == "expense")
            
            daily_flow.append({
                "date": day_date.date().isoformat(),
                "income": day_income,
                "expenses": day_expenses,
                "net": day_income - day_expenses
            })
        
        return MonthlyReport(
            month=f"{year}-{month:02d}",
            income=income,
            expenses=expenses,
            savings=savings,
            top_categories=top_categories,
            daily_flow=daily_flow
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/yearly/{year}")
async def get_yearly_report(year: int, db: Session = Depends(get_db)):
    """Get yearly financial report"""
    try:
        # Get all transactions for the year
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)
        
        transactions = db.query(Transaction).filter(
            Transaction.timestamp >= start_date,
            Transaction.timestamp < end_date
        ).all()
        
        # Calculate yearly totals
        yearly_income = sum(t.amount for t in transactions if t.transaction_type.value == "income")
        yearly_expenses = sum(t.amount for t in transactions if t.transaction_type.value == "expense")
        yearly_savings = yearly_income - yearly_expenses
        
        # Monthly breakdown
        monthly_data = {}
        for month in range(1, 13):
            monthly_data[month] = {"income": 0, "expenses": 0, "savings": 0}
        
        for transaction in transactions:
            month = transaction.timestamp.month
            if transaction.transaction_type.value == "income":
                monthly_data[month]["income"] += transaction.amount
            else:
                monthly_data[month]["expenses"] += transaction.amount
        
        # Calculate savings for each month
        for month in monthly_data:
            monthly_data[month]["savings"] = monthly_data[month]["income"] - monthly_data[month]["expenses"]
        
        # Category analysis
        category_analysis = {}
        for transaction in transactions:
            if transaction.category:
                cat_name = transaction.category.name
                if cat_name not in category_analysis:
                    category_analysis[cat_name] = {"income": 0, "expenses": 0, "transactions": 0}
                
                category_analysis[cat_name]["transactions"] += 1
                if transaction.transaction_type.value == "income":
                    category_analysis[cat_name]["income"] += transaction.amount
                else:
                    category_analysis[cat_name]["expenses"] += transaction.amount
        
        # Sort categories by total activity
        sorted_categories = sorted(
            category_analysis.items(),
            key=lambda x: x[1]["income"] + x[1]["expenses"],
            reverse=True
        )
        
        return {
            "year": year,
            "summary": {
                "total_income": yearly_income,
                "total_expenses": yearly_expenses,
                "total_savings": yearly_savings,
                "savings_rate": (yearly_savings / yearly_income * 100) if yearly_income > 0 else 0,
                "transaction_count": len(transactions)
            },
            "monthly_breakdown": [
                {
                    "month": f"{year}-{month:02d}",
                    "month_name": calendar.month_name[month],
                    "income": monthly_data[month]["income"],
                    "expenses": monthly_data[month]["expenses"],
                    "savings": monthly_data[month]["savings"]
                }
                for month in range(1, 13)
            ],
            "top_categories": [
                {
                    "category": category,
                    "income": data["income"],
                    "expenses": data["expenses"],
                    "total_activity": data["income"] + data["expenses"],
                    "transaction_count": data["transactions"]
                }
                for category, data in sorted_categories[:15]
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monthly-export", response_model=ResponseModel)
async def export_monthly_report(
    db: Session = Depends(get_db),
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$")
):
    """Export monthly report to Google Sheets"""
    try:
        year, month_num = map(int, month.split('-'))
        
        # Get monthly data
        start_date = datetime(year, month_num, 1)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month_num + 1, 1)
        
        transactions = db.query(Transaction).filter(
            Transaction.timestamp >= start_date,
            Transaction.timestamp < end_date
        ).all()
        
        budgets = db.query(Budget).filter(Budget.month == month).all()
        
        # Export to Google Sheets
        success = await gsheets_service.export_monthly_report(
            year, month_num, transactions, budgets
        )
        
        if success:
            return ResponseModel(
                success=True,
                message=f"Monthly report for {month} exported to Google Sheets"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to export to Google Sheets")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/insights")
async def get_financial_insights(db: Session = Depends(get_db)):
    """Get AI-powered financial insights and recommendations"""
    try:
        now = datetime.now()
        
        # Get last 3 months of data
        three_months_ago = now - timedelta(days=90)
        recent_transactions = db.query(Transaction).filter(
            Transaction.timestamp >= three_months_ago
        ).all()
        
        # Calculate spending patterns
        spending_by_day_of_week = [0] * 7  # Monday = 0, Sunday = 6
        spending_by_hour = [0] * 24
        category_trends = {}
        
        for transaction in recent_transactions:
            if transaction.transaction_type.value == "expense":
                # Day of week analysis
                day_of_week = transaction.timestamp.weekday()
                spending_by_day_of_week[day_of_week] += transaction.amount
                
                # Hour analysis
                hour = transaction.timestamp.hour
                spending_by_hour[hour] += transaction.amount
                
                # Category trends
                if transaction.category:
                    cat_name = transaction.category.name
                    month_key = transaction.timestamp.strftime("%Y-%m")
                    
                    if cat_name not in category_trends:
                        category_trends[cat_name] = {}
                    
                    if month_key not in category_trends[cat_name]:
                        category_trends[cat_name][month_key] = 0
                    
                    category_trends[cat_name][month_key] += transaction.amount
        
        # Generate insights
        insights = []
        
        # Peak spending day
        peak_day_idx = spending_by_day_of_week.index(max(spending_by_day_of_week))
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        insights.append({
            "type": "spending_pattern",
            "title": "Peak Spending Day",
            "message": f"You spend the most on {day_names[peak_day_idx]}",
            "data": {"day": day_names[peak_day_idx], "amount": spending_by_day_of_week[peak_day_idx]}
        })
        
        # Peak spending hour
        peak_hour = spending_by_hour.index(max(spending_by_hour))
        insights.append({
            "type": "spending_pattern",
            "title": "Peak Spending Hour",
            "message": f"Most spending occurs at {peak_hour:02d}:00",
            "data": {"hour": peak_hour, "amount": spending_by_hour[peak_hour]}
        })
        
        # Category growth/decline
        for category, monthly_data in category_trends.items():
            if len(monthly_data) >= 2:
                months = sorted(monthly_data.keys())
                latest_month = monthly_data[months[-1]]
                previous_month = monthly_data[months[-2]]
                
                if previous_month > 0:
                    change_percent = ((latest_month - previous_month) / previous_month) * 100
                    
                    if abs(change_percent) > 20:  # Significant change
                        trend = "increased" if change_percent > 0 else "decreased"
                        insights.append({
                            "type": "category_trend",
                            "title": f"{category} Spending {trend.title()}",
                            "message": f"Your {category} spending has {trend} by {abs(change_percent):.1f}%",
                            "data": {
                                "category": category,
                                "change_percent": change_percent,
                                "previous": previous_month,
                                "current": latest_month
                            }
                        })
        
        return {
            "insights": insights,
            "spending_patterns": {
                "by_day_of_week": {
                    day_names[i]: spending_by_day_of_week[i] 
                    for i in range(7)
                },
                "by_hour": {f"{i:02d}:00": spending_by_hour[i] for i in range(24)},
                "peak_spending_day": day_names[peak_day_idx],
                "peak_spending_hour": f"{peak_hour:02d}:00"
            },
            "category_trends": category_trends,
            "analysis_period": {
                "start": three_months_ago,
                "end": now
            },  
            "transaction_count": len(recent_transactions)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))