import os, logging
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
from typing import List, Dict, Optional
import asyncio
from fastapi import Request

class GoogleSheetsService:
    def __init__(self, cred_path: str = "config/google_credentials.json"):
        self.client = None
        self.init_error = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.credentials_path = cred_path
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
            self.client = gspread.authorize(creds)
        except Exception as e:
            logging.exception("Failed to init Google Sheets client")
            self.init_error = e
            self.client = None

        # prefer configured spreadsheet ID to avoid create()
        self.spreadsheet_id = os.environ.get("GSHEET_ID")
        # default sheet name for transactions (can be overridden with env GSHEET_TRANSACTIONS_SHEET)
        self.TRANSACTIONS_SHEET = os.environ.get("GSHEET_TRANSACTIONS_SHEET", "Transactions")
        self.BUDGETS_SHEET = os.environ.get("GSHEET_BUDGETS_SHEET", "Budgets")
        self.SUMMARY_SHEET = os.environ.get("GSHEET_SUMMARY_SHEET", "Summary")
        self.spreadsheet = None
        if self.client and self.spreadsheet_id:
            try:
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            except Exception:
                logging.exception("Failed to open configured spreadsheet with GSHEET_ID")


    async def initialize(self):
        """Initialize Google Sheets client with proper error handling"""
        try:
            if self.client:
                return True  # Already initialized
                
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                self.executor,
                self._initialize_client
            )
            
            if not success:
                self.init_error = "Failed to initialize Google Sheets client"
                return False
                
            # Verify spreadsheet access
            if not self.spreadsheet_id:
                self.init_error = "No spreadsheet ID configured"
                return False
                
            try:
                await loop.run_in_executor(
                    self.executor,
                    lambda: self.client.open_by_key(self.spreadsheet_id)
                )
            except Exception as e:
                self.init_error = f"Cannot access spreadsheet: {str(e)}"
                return False
                
            return True
            
        except Exception as e:
            self.init_error = str(e)
            return False
        if not self.client:
            try:
                # Define the scope
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
                
                # Load credentials
                creds = Credentials.from_service_account_file(self.credentials_path, scopes=scope)
                self.client = gspread.authorize(creds)
                
                # Open or create spreadsheet
                if self.spreadsheet_id:
                    self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                else:
                    # Create new spreadsheet
                    self.spreadsheet = self.client.create("FinHelper - Personal Finance")
                    print(f"Created new spreadsheet: {self.spreadsheet.url}")
                    
                # Setup sheets structure
                await self._setup_sheets()
                return True
                
            except Exception as e:
                print(f"Failed to initialize Google Sheets: {e}")
                return False
    
    async def _setup_sheets(self):
        """Setup the required sheets structure"""
        try:
            # Get existing worksheets
            existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            
            # Create Transactions sheet
            if self.TRANSACTIONS_SHEET not in existing_sheets:
                transactions_sheet = self.spreadsheet.add_worksheet(
                    title=self.TRANSACTIONS_SHEET, rows=1000, cols=10
                )
                # Add headers
                headers = [
                    "Date", "Amount", "Type", "Category", "Merchant", 
                    "Description", "Account", "Source", "ID", "Created"
                ]
                transactions_sheet.append_row(headers)
            
            # Create Budgets sheet
            if self.BUDGETS_SHEET not in existing_sheets:
                budgets_sheet = self.spreadsheet.add_worksheet(
                    title=self.BUDGETS_SHEET, rows=100, cols=8
                )
                headers = [
                    "Month", "Category", "Budget Limit", "Amount Spent", 
                    "Remaining", "Percentage Used", "Alert Threshold", "Status"
                ]
                budgets_sheet.append_row(headers)
            
            # Create Summary sheet
            if self.SUMMARY_SHEET not in existing_sheets:
                summary_sheet = self.spreadsheet.add_worksheet(
                    title=self.SUMMARY_SHEET, rows=100, cols=6
                )
                headers = ["Metric", "Value", "Period", "Last Updated", "Notes", "Trend"]
                summary_sheet.append_row(headers)
                
                # Add initial summary rows
                initial_data = [
                    ["Total Balance", "=SUMIF(Transactions!C:C,\"income\",Transactions!B:B)-SUMIF(Transactions!C:C,\"expense\",Transactions!B:B)", "All Time", "", "Current total balance across all accounts", ""],
                    ["Monthly Income", "=SUMIFS(Transactions!B:B,Transactions!C:C,\"income\",Transactions!A:A,\">\"&EOMONTH(TODAY(),-1),Transactions!A:A,\"<=\"&EOMONTH(TODAY(),0))", "Current Month", "", "Income for current month", ""],
                    ["Monthly Expenses", "=SUMIFS(Transactions!B:B,Transactions!C:C,\"expense\",Transactions!A:A,\">\"&EOMONTH(TODAY(),-1),Transactions!A:A,\"<=\"&EOMONTH(TODAY(),0))", "Current Month", "", "Expenses for current month", ""],
                    ["Monthly Savings", "=B2-B3", "Current Month", "", "Net savings for current month", ""]
                ]
                
                for row in initial_data:
                    summary_sheet.append_row(row)
            
            print("Google Sheets structure setup completed")
            
        except Exception as e:
            print(f"Error setting up sheets: {e}")
    
    async def add_transaction(self, transaction):
        """Add a transaction to the Transactions sheet"""
        if not self.client or not self.spreadsheet:
            success = await self.initialize()
            if not success:
                return False
                
        try:
            # Prepare transaction data
            row_data = [
                transaction.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                transaction.amount,
                transaction.transaction_type.value,
                transaction.category.name if transaction.category else "Uncategorized",
                transaction.merchant or "",
                transaction.description or "",
                transaction.account.name if transaction.account else "Unknown",
                transaction.source.value,
                transaction.id,
                transaction.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            # Add to sheet (run in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._append_row_to_sheet,
                self.TRANSACTIONS_SHEET,
                row_data
            )
            
            # Update summary after adding transaction
            await self._update_summary()
            
            return True
            
        except Exception as e:
            print(f"Error adding transaction to sheets: {e}")
            return False
    
    def _append_row_to_sheet(self, sheet_name: str, row_data: List):
        """Helper method to append row to sheet (runs in thread)"""
        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
            sheet.append_row(row_data)
        except Exception as e:
            print(f"Error appending to {sheet_name}: {e}")
            raise
    
    async def update_budget_sheet(self, budgets: List):
        """Update the Budgets sheet with current budget data"""
        if not self.client:
            await self.initialize()
            
        if not self.client:
            return False
            
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._update_budgets_sync,
                budgets
            )
            return True
            
        except Exception as e:
            print(f"Error updating budget sheet: {e}")
            return False
    
    def _update_budgets_sync(self, budgets):
        """Synchronous budget update method"""
        try:
            sheet = self.spreadsheet.worksheet(self.BUDGETS_SHEET)
            
            # Clear existing data (keep headers)
            sheet.clear()
            headers = [
                "Month", "Category", "Budget Limit", "Amount Spent", 
                "Remaining", "Percentage Used", "Alert Threshold", "Status"
            ]
            sheet.append_row(headers)
            
            # Add budget data
            for budget in budgets:
                # replace the broken conditional expression with an explicit if/else
                if getattr(budget, "amount_limit", 0) and budget.amount_limit > 0:
                    percentage_used = (budget.amount_spent / budget.amount_limit) * 100
                else:
                    percentage_used = 0
                remaining = budget.amount_limit - budget.amount_spent
                status = "⚠️ Over Budget" if percentage_used > 100 else "✅ On Track" if percentage_used < budget.alert_threshold * 100 else "⚠️ Near Limit"
                
                row_data = [
                    budget.month,
                    budget.category.name if budget.category else "Unknown",
                    budget.amount_limit,
                    budget.amount_spent,
                    remaining,
                    f"{percentage_used:.1f}%",
                    f"{budget.alert_threshold * 100:.0f}%",
                    status
                ]
                sheet.append_row(row_data)
                
        except Exception as e:
            print(f"Error in _update_budgets_sync: {e}")
            raise
    
    async def _update_summary(self):
        """Update the Summary sheet with current timestamp"""
        try:
            if not self.client:
                return
                
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._update_summary_sync
            )
            
        except Exception as e:
            print(f"Error updating summary: {e}")
    
    def _update_summary_sync(self):
        """Synchronous summary update method"""
        try:
            sheet = self.spreadsheet.worksheet(self.SUMMARY_SHEET)
            
            # Update "Last Updated" column (column D) for all rows
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get all rows and update timestamp
            all_values = sheet.get_all_values()
            if len(all_values) > 1:  # Skip header row
                for i in range(2, len(all_values) + 1):  # Start from row 2
                    sheet.update(f'D{i}', current_time)
                    
        except Exception as e:
            print(f"Error in _update_summary_sync: {e}")
            raise
    
    async def export_monthly_report(self, year: int, month: int, transactions: List, budgets: List):
        """Export comprehensive monthly report to a new sheet"""
        if not self.client or not self.spreadsheet:
            success = await self.initialize()
            if not success:
                return False
            
        try:
            sheet_name = f"Report_{year}_{month:02d}"
            
            # Check if sheet already exists
            try:
                report_sheet = self.spreadsheet.worksheet(sheet_name)
                # Clear existing content
                report_sheet.clear()
            except:
                # Create new sheet
                report_sheet = self.spreadsheet.add_worksheet(
                    title=sheet_name, rows=500, cols=10
                )
            
            # Prepare report data
            report_data = self._prepare_monthly_report_data(year, month, transactions, budgets)
            
            # Add data to sheet
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._write_monthly_report,
                report_sheet,
                report_data
            )
            
            return True
            
        except Exception as e:
            print(f"Error exporting monthly report: {e}")
            return False
    
    def _prepare_monthly_report_data(self, year: int, month: int, transactions: List, budgets: List):
        """Prepare monthly report data structure"""
        # Calculate totals
        income = sum(t.amount for t in transactions if t.transaction_type.value == "income")
        expenses = sum(t.amount for t in transactions if t.transaction_type.value == "expense")
        savings = income - expenses
        
        # Category breakdown
        category_expenses = {}
        for t in transactions:
            if t.transaction_type.value == "expense" and t.category:
                cat_name = t.category.name
                category_expenses[cat_name] = category_expenses.get(cat_name, 0) + t.amount
        
        # Top merchants
        merchant_expenses = {}
        for t in transactions:
            if t.transaction_type.value == "expense" and t.merchant:
                merchant_expenses[t.merchant] = merchant_expenses.get(t.merchant, 0) + t.amount
        
        top_merchants = sorted(merchant_expenses.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "month": f"{year}-{month:02d}",
            "totals": {"income": income, "expenses": expenses, "savings": savings},
            "categories": category_expenses,
            "top_merchants": top_merchants,
            "budgets": budgets,
            "transaction_count": len(transactions)
        }
    
    def _write_monthly_report(self, sheet, report_data):
        """Write monthly report data to sheet"""
        try:
            # Header
            sheet.append_row([f"Monthly Financial Report - {report_data['month']}", "", "", "", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
            sheet.append_row([])
            
            # Summary section
            sheet.append_row(["FINANCIAL SUMMARY"])
            sheet.append_row(["Income", f"Rp {report_data['totals']['income']:,.0f}"])
            sheet.append_row(["Expenses", f"Rp {report_data['totals']['expenses']:,.0f}"])
            sheet.append_row(["Net Savings", f"Rp {report_data['totals']['savings']:,.0f}"])
            sheet.append_row(["Transaction Count", report_data['transaction_count']])
            sheet.append_row([])

            # Monthly Comparison section
            sheet.append_row(["MONTHLY COMPARISON"])
            sheet.append_row(["Month", "Income", "Expenses", "Net Savings"])
            
            # Get previous month data
            if report_data['month'] != "2023-01":  # Avoid referencing invalid month
                prev_year = year
                prev_month = month - 1
                if prev_month == 0:
                    prev_year -= 1
                    prev_month = 12
                
                prev_month_str = f"{prev_year}-{prev_month:02d}"
                prev_month_data = self._prepare_monthly_report_data(prev_year, prev_month, transactions, budgets)
                
                sheet.append_row([prev_month_str, f"Rp {prev_month_data['totals']['income']:,.0f}", f"Rp {prev_month_data['totals']['expenses']:,.0f}", f"Rp {prev_month_data['totals']['savings']:,.0f}"])
            
            # Add current month data
            sheet.append_row([report_data['month'], f"Rp {report_data['totals']['income']:,.0f}", f"Rp {report_data['totals']['expenses']:,.0f}", f"Rp {report_data['totals']['savings']:,.0f}"])
            
            sheet.append_row([])

            # Category breakdown
            sheet.append_row(["EXPENSES BY CATEGORY"])
            sheet.append_row(["Category", "Amount", "Percentage"])
            
            total_expenses = report_data['totals']['expenses']
            for category, amount in sorted(report_data['categories'].items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                sheet.append_row([category, f"Rp {amount:,.0f}", f"{percentage:.1f}%"])
            
            sheet.append_row([])

            # Top merchants
            sheet.append_row(["TOP MERCHANTS"])
            sheet.append_row(["Merchant", "Amount"])
            for merchant, amount in report_data['top_merchants']:
                sheet.append_row([merchant, f"Rp {amount:,.0f}"])
            
            sheet.append_row([])

            # Budget performance
            sheet.append_row(["BUDGET PERFORMANCE"])
            sheet.append_row(["Category", "Budget", "Spent", "Remaining", "% Used"])
            for budget in report_data['budgets']:
                percentage_used = (budget.amount_spent / budget.amount_limit * 100) if budget.amount_limit > 0 else 0
                remaining = budget.amount_limit - budget.amount_spent
                status = "⚠️ Over Budget" if percentage_used > 100 else "✅ On Track" if percentage_used < budget.alert_threshold * 100 else "⚠️ Near Limit"
                
                sheet.append_row([
                    budget.category.name if budget.category else "Unknown",
                    f"Rp {budget.amount_limit:,.0f}",
                    f"Rp {budget.amount_spent:,.0f}",
                    f"Rp {remaining:,.0f}",
                    f"{percentage_used:.1f}%"
                ])
            
            # Formatting
            sheet.set_column_widths([
                (1, 20),   # Month
                (2, 30),   # Category
                (3, 15),   # Budget Limit
                (4, 15),   # Amount Spent
                (5, 15),   # Remaining
                (6, 20),   # % Used
                (7, 25),   # Status
                (8, 10)    # Empty column
            ])
            
            # Freeze header row
            sheet.freeze(rows=1)
            
        except Exception as e:
            print(f"Error writing monthly report: {e}")
            raise

# Di bagian bawah file
def get_sheets_service(request: Request):
    service = request.app.state.sheets_service
    if not service or not service.client:
        # Coba inisialisasi ulang jika belum berhasil
        service = GoogleSheetsService()
        asyncio.create_task(service.initialize())
    return service