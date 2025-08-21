from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta

from app.models import get_db, Budget, Transaction, Category
from app.schemas import (
    BudgetCreate, BudgetUpdate, Budget as BudgetSchema,
    ResponseModel
)
from app.services.gsheets_service import GoogleSheetsService

router = APIRouter()
gsheets_service = GoogleSheetsService()

@router.post("/", response_model=ResponseModel)
async def create_budget(
    budget: BudgetCreate,
    db: Session = Depends(get_db)
):
    """Create a new budget"""
    try:
        # Check if budget already exists for this category and month
        existing_budget = db.query(Budget).filter(
            Budget.category_id == budget.category_id,
            Budget.month == budget.month
        ).first()
        
        if existing_budget:
            raise HTTPException(
                status_code=400, 
                detail="Budget already exists for this category and month"
            )
        
        # Verify category exists
        category = db.query(Category).filter(Category.id == budget.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        
        # Create budget
        db_budget = Budget(**budget.dict())
        
        # Calculate current spending for this month/category
        current_spending = await _calculate_current_spending(
            db, budget.category_id, budget.month
        )
        db_budget.amount_spent = current_spending
        
        db.add(db_budget)
        db.commit()
        db.refresh(db_budget)
        
        # Sync to Google Sheets
        try:
            budgets = db.query(Budget).filter(Budget.is_active == True).all()
            await gsheets_service.update_budget_sheet(budgets)
        except Exception as e:
            print(f"Failed to sync budgets to sheets: {e}")
        
        return ResponseModel(
            success=True,
            message="Budget created successfully",
            data={"budget_id": db_budget.id}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[BudgetSchema])
async def get_budgets(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    category_id: Optional[int] = Query(None),
    active_only: bool = Query(True)
):
    """Get budgets with optional filters"""
    query = db.query(Budget)
    
    if month:
        query = query.filter(Budget.month == month)
    if category_id:
        query = query.filter(Budget.category_id == category_id)
    if active_only:
        query = query.filter(Budget.is_active == True)
    
    budgets = query.order_by(Budget.month.desc(), Budget.created_at.desc()).all()
    
    # Update spending amounts
    for budget in budgets:
        current_spending = await _calculate_current_spending(
            db, budget.category_id, budget.month
        )
        if budget.amount_spent != current_spending:
            budget.amount_spent = current_spending
    
    db.commit()
    return budgets

@router.get("/{budget_id}", response_model=BudgetSchema)
async def get_budget(budget_id: int, db: Session = Depends(get_db)):
    """Get specific budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Update spending amount
    current_spending = await _calculate_current_spending(
        db, budget.category_id, budget.month
    )
    if budget.amount_spent != current_spending:
        budget.amount_spent = current_spending
        db.commit()
    
    return budget

@router.put("/{budget_id}", response_model=ResponseModel)
async def update_budget(
    budget_id: int,
    budget_update: BudgetUpdate,
    db: Session = Depends(get_db)
):
    """Update a budget"""
    try:
        db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
        if not db_budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        # Update budget fields
        update_data = budget_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_budget, field, value)
        
        # Recalculate spending
        current_spending = await _calculate_current_spending(
            db, db_budget.category_id, db_budget.month
        )
        db_budget.amount_spent = current_spending
        
        db.commit()
        
        # Sync to Google Sheets
        try:
            budgets = db.query(Budget).filter(Budget.is_active == True).all()
            await gsheets_service.update_budget_sheet(budgets)
        except Exception as e:
            print(f"Failed to sync budgets to sheets: {e}")
        
        return ResponseModel(
            success=True,
            message="Budget updated successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{budget_id}", response_model=ResponseModel)
async def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    """Delete a budget"""
    try:
        db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
        if not db_budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        db.delete(db_budget)
        db.commit()
        
        return ResponseModel(
            success=True,
            message="Budget deleted successfully"
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/current/status")
async def get_current_budget_status(db: Session = Depends(get_db)):
    """Get current month budget status"""
    current_month = datetime.now().strftime("%Y-%m")
    
    budgets = db.query(Budget).filter(
        Budget.month == current_month,
        Budget.is_active == True
    ).all()
    
    # Update spending amounts and calculate status
    budget_status = []
    total_budget = 0
    total_spent = 0
    alerts = []
    
    for budget in budgets:
        current_spending = await _calculate_current_spending(
            db, budget.category_id, budget.month
        )
        budget.amount_spent = current_spending
        
        percentage_used = (current_spending / budget.amount_limit) * 100 if budget.amount_limit > 0 else 0
        remaining = budget.amount_limit - current_spending
        
        status = "over_budget" if percentage_used > 100 else \
                "near_limit" if percentage_used >= budget.alert_threshold * 100 else \
                "on_track"
        
        budget_info = {
            "id": budget.id,
            "category": budget.category.name if budget.category else "Unknown",
            "budget_limit": budget.amount_limit,
            "amount_spent": current_spending,
            "remaining": remaining,
            "percentage_used": round(percentage_used, 1),
            "status": status
        }
        
        budget_status.append(budget_info)
        total_budget += budget.amount_limit
        total_spent += current_spending
        
        # Check for alerts
        if status in ["over_budget", "near_limit"]:
            alerts.append({
                "type": "budget_alert",
                "category": budget.category.name if budget.category else "Unknown",
                "message": f"Budget {status.replace('_', ' ')} for {budget.category.name if budget.category else 'Unknown'}",
                "percentage": round(percentage_used, 1),
                "amount_over": max(0, current_spending - budget.amount_limit)
            })
    
    db.commit()
    
    return {
        "month": current_month,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "overall_percentage": round((total_spent / total_budget) * 100, 1) if total_budget > 0 else 0,
        "budgets": budget_status,
        "alerts": alerts,
        "budget_count": len(budgets)
    }

@router.post("/refresh-spending", response_model=ResponseModel)
async def refresh_budget_spending(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$")
):
    """Refresh spending amounts for budgets"""
    try:
        query = db.query(Budget).filter(Budget.is_active == True)
        if month:
            query = query.filter(Budget.month == month)
        
        budgets = query.all()
        updated_count = 0
        
        for budget in budgets:
            old_spending = budget.amount_spent
            current_spending = await _calculate_current_spending(
                db, budget.category_id, budget.month
            )
            
            if old_spending != current_spending:
                budget.amount_spent = current_spending
                updated_count += 1
        
        db.commit()
        
        # Sync to Google Sheets
        if updated_count > 0:
            try:
                await gsheets_service.update_budget_sheet(budgets)
            except Exception as e:
                print(f"Failed to sync budgets to sheets: {e}")
        
        return ResponseModel(
            success=True,
            message=f"Refreshed spending for {updated_count} budgets",
            data={"updated_count": updated_count}
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/trends")
async def get_budget_trends(
    db: Session = Depends(get_db),
    months: int = Query(6, ge=1, le=24)
):
    """Get budget trends over multiple months"""
    try:
        # Get recent months
        current_date = datetime.now()
        month_list = []
        
        for i in range(months):
            month_date = current_date.replace(day=1) - timedelta(days=i*30)
            month_str = month_date.strftime("%Y-%m")
            month_list.append(month_str)
        
        month_list.reverse()
        
        # Get budget data for these months
        trends = {}
        
        for month in month_list:
            budgets = db.query(Budget).filter(Budget.month == month).all()
            
            total_budget = sum(b.amount_limit for b in budgets)
            total_spent = 0
            category_data = {}
            
            for budget in budgets:
                spending = await _calculate_current_spending(
                    db, budget.category_id, month
                )
                total_spent += spending
                
                if budget.category:
                    category_data[budget.category.name] = {
                        "budget": budget.amount_limit,
                        "spent": spending,
                        "percentage": (spending / budget.amount_limit * 100) if budget.amount_limit > 0 else 0
                    }
            
            trends[month] = {
                "total_budget": total_budget,
                "total_spent": total_spent,
                "savings": total_budget - total_spent,
                "adherence_rate": ((total_budget - total_spent) / total_budget * 100) if total_budget > 0 else 100,
                "categories": category_data,
                "budget_count": len(budgets)
            }
        
        return {
            "months": month_list,
            "trends": trends,
            "summary": _calculate_trend_summary(trends)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _calculate_current_spending(db: Session, category_id: int, month: str) -> float:
    """Calculate current spending for a category in a specific month"""
    try:
        # Parse month (YYYY-MM)
        year, month_num = map(int, month.split('-'))
        
        # Calculate date range
        start_date = datetime(year, month_num, 1)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month_num + 1, 1)
        
        # Query transactions
        spending = db.query(func.sum(Transaction.amount)).filter(
            Transaction.category_id == category_id,
            Transaction.transaction_type == "expense",
            Transaction.timestamp >= start_date,
            Transaction.timestamp < end_date
        ).scalar()
        
        return spending or 0.0
    
    except Exception as e:
        print(f"Error calculating spending: {e}")
        return 0.0

def _calculate_trend_summary(trends: dict) -> dict:
    """Calculate summary statistics from trend data"""
    if not trends:
        return {}
    
    months = list(trends.keys())
    
    # Calculate averages
    avg_budget = sum(trends[m]["total_budget"] for m in months) / len(months)
    avg_spent = sum(trends[m]["total_spent"] for m in months) / len(months)
    avg_adherence = sum(trends[m]["adherence_rate"] for m in months) / len(months)
    
    # Calculate trends (comparing first half vs second half)
    half_point = len(months) // 2
    first_half = months[:half_point]
    second_half = months[half_point:]
    
    if first_half and second_half:
        first_half_avg_spent = sum(trends[m]["total_spent"] for m in first_half) / len(first_half)
        second_half_avg_spent = sum(trends[m]["total_spent"] for m in second_half) / len(second_half)
        
        spending_trend = "increasing" if second_half_avg_spent > first_half_avg_spent else \
                        "decreasing" if second_half_avg_spent < first_half_avg_spent else "stable"
        
        trend_percentage = ((second_half_avg_spent - first_half_avg_spent) / first_half_avg_spent * 100) \
                          if first_half_avg_spent > 0 else 0
    else:
        spending_trend = "stable"
        trend_percentage = 0
    
    return {
        "average_budget": round(avg_budget, 2),
        "average_spent": round(avg_spent, 2),
        "average_adherence_rate": round(avg_adherence, 2),
        "spending_trend": spending_trend,
        "trend_percentage": round(trend_percentage, 2),
        "best_month": max(months, key=lambda m: trends[m]["adherence_rate"]),
        "worst_month": min(months, key=lambda m: trends[m]["adherence_rate"])
    }