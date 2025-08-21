import re
import yaml
import os
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.models import Category

class AutoCategorizer:
    def __init__(self):
        self.rules_file = "config/categorization_rules.yaml"
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict:
        """Load categorization rules from YAML file"""
        default_rules = {
            "food_and_dining": {
                "keywords": ["grab", "gojek", "mcdonald", "kfc", "starbucks", "restoran", "warung", "bakso", "nasi", "ayam"],
                "patterns": [r"grab.*food", r"go.*food", r".*restaurant.*", r".*cafe.*"],
                "category_name": "Food & Dining"
            },
            "transportation": {
                "keywords": ["grab.*car", "grab.*bike", "gojek.*ride", "uber", "taxi", "ojek", "angkot", "transjakarta", "mrt", "krl"],
                "patterns": [r"grab.*ride", r"go.*ride", r".*transport.*", r".*taxi.*"],
                "category_name": "Transportation"
            },
            "shopping": {
                "keywords": ["tokopedia", "shopee", "lazada", "blibli", "amazon", "mall", "supermarket", "indomaret", "alfamart"],
                "patterns": [r".*shop.*", r".*market.*", r".*store.*"],
                "category_name": "Shopping"
            },
            "utilities": {
                "keywords": ["pln", "listrik", "air", "pdam", "internet", "wifi", "telkom", "indihome", "gas", "pgas"],
                "patterns": [r".*electric.*", r".*water.*", r".*internet.*", r".*gas.*"],
                "category_name": "Utilities"
            },
            "healthcare": {
                "keywords": ["hospital", "rumah sakit", "dokter", "apotik", "farmasi", "obat", "medical", "klinik"],
                "patterns": [r".*hospital.*", r".*medical.*", r".*pharmacy.*"],
                "category_name": "Healthcare"
            },
            "entertainment": {
                "keywords": ["netflix", "spotify", "cinema", "bioskop", "game", "steam", "playstation", "xbox"],
                "patterns": [r".*entertainment.*", r".*movie.*", r".*music.*", r".*game.*"],
                "category_name": "Entertainment"
            },
            "education": {
                "keywords": ["sekolah", "universitas", "kursus", "course", "training", "seminar", "buku", "book"],
                "patterns": [r".*school.*", r".*university.*", r".*course.*", r".*training.*"],
                "category_name": "Education"
            },
            "income_salary": {
                "keywords": ["gaji", "salary", "bonus", "tunjangan", "allowance", "payroll"],
                "patterns": [r".*salary.*", r".*payroll.*", r".*income.*"],
                "category_name": "Salary",
                "transaction_type": "income"
            },
            "income_investment": {
                "keywords": ["dividend", "dividen", "bunga", "interest", "profit", "keuntungan", "return"],
                "patterns": [r".*dividend.*", r".*interest.*", r".*return.*"],
                "category_name": "Investment Return",
                "transaction_type": "income"
            }
        }
        
        if os.path.exists(self.rules_file):
            try:
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    loaded_rules = yaml.safe_load(f)
                    if loaded_rules:
                        return loaded_rules
            except Exception as e:
                print(f"Error loading categorization rules: {e}")
        
        # Create default rules file if not exists
        os.makedirs("config", exist_ok=True)
        with open(self.rules_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_rules, f, default_flow_style=False, allow_unicode=True)
        
        return default_rules
    
    async def categorize_transaction(
        self, 
        merchant: Optional[str] = None, 
        description: Optional[str] = None, 
        amount: float = 0,
        db: Session = None
    ) -> Optional[int]:
        """
        Auto-categorize a transaction based on merchant name and description
        Returns category_id if found, None otherwise
        """
        if not merchant and not description:
            return None
        
        text_to_analyze = f"{merchant or ''} {description or ''}".lower().strip()
        
        if not text_to_analyze:
            return None
        
        # Try to match against rules
        for rule_key, rule in self.rules.items():
            if self._matches_rule(text_to_analyze, rule):
                category_name = rule.get("category_name")
                if category_name:
                    category = await self._get_or_create_category(category_name, db)
                    if category:
                        return category.id
        
        return None
    
    def _matches_rule(self, text: str, rule: Dict) -> bool:
        """Check if text matches a categorization rule"""
        # Check keywords
        keywords = rule.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in text:
                return True
        
        # Check regex patterns
        patterns = rule.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern.lower(), text, re.IGNORECASE):
                return True
        
        return False
    
    async def _get_or_create_category(self, category_name: str, db: Session) -> Optional[Category]:
        """Get existing category or create new one"""
        if not db:
            return None
        
        try:
            # Try to find existing category
            category = db.query(Category).filter(Category.name == category_name).first()
            
            if not category:
                # Create new category
                category = Category(name=category_name, is_active=True)
                db.add(category)
                db.commit()
                db.refresh(category)
            
            return category
        
        except Exception as e:
            print(f"Error getting/creating category {category_name}: {e}")
            db.rollback()
            return None
    
    def add_custom_rule(self, rule_name: str, keywords: List[str], patterns: List[str], category_name: str):
        """Add a custom categorization rule"""
        self.rules[rule_name] = {
            "keywords": keywords,
            "patterns": patterns,
            "category_name": category_name
        }
        
        # Save to file
        try:
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.rules, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Error saving custom rule: {e}")
    
    def get_all_rules(self) -> Dict:
        """Get all categorization rules"""
        return self.rules
    
    def update_rule(self, rule_name: str, updated_rule: Dict):
        """Update an existing rule"""
        if rule_name in self.rules:
            self.rules[rule_name].update(updated_rule)
            
            # Save to file
            try:
                with open(self.rules_file, 'w', encoding='utf-8') as f:
                    yaml.dump(self.rules, f, default_flow_style=False, allow_unicode=True)
            except Exception as e:
                print(f"Error updating rule: {e}")
    
    def delete_rule(self, rule_name: str):
        """Delete a categorization rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            
            # Save to file
            try:
                with open(self.rules_file, 'w', encoding='utf-8') as f:
                    yaml.dump(self.rules, f, default_flow_style=False, allow_unicode=True)
            except Exception as e:
                print(f"Error deleting rule: {e}")
    
    async def bulk_categorize_transactions(self, db: Session, limit: int = 100):
        """
        Bulk categorize uncategorized transactions
        Returns number of transactions categorized
        """
        from app.models import Transaction
        
        try:
            # Get uncategorized transactions
            uncategorized_transactions = db.query(Transaction).filter(
                Transaction.category_id.is_(None)
            ).limit(limit).all()
            
            categorized_count = 0
            
            for transaction in uncategorized_transactions:
                category_id = await self.categorize_transaction(
                    merchant=transaction.merchant,
                    description=transaction.description,
                    amount=transaction.amount,
                    db=db
                )
                
                if category_id:
                    transaction.category_id = category_id
                    categorized_count += 1
            
            if categorized_count > 0:
                db.commit()
            
            return categorized_count
        
        except Exception as e:
            print(f"Error in bulk categorization: {e}")
            db.rollback()
            return 0
    
    def suggest_categories_for_merchant(self, merchant: str) -> List[str]:
        """
        Suggest possible categories for a merchant
        Returns list of category names that might match
        """
        if not merchant:
            return []
        
        merchant_lower = merchant.lower()
        suggestions = []
        
        for rule_key, rule in self.rules.items():
            if self._matches_rule(merchant_lower, rule):
                category_name = rule.get("category_name")
                if category_name and category_name not in suggestions:
                    suggestions.append(category_name)
        
        return suggestions
    
    def get_categorization_stats(self, db: Session) -> Dict:
        """Get statistics about categorization coverage"""
        from app.models import Transaction
        
        try:
            total_transactions = db.query(Transaction).count()
            categorized_transactions = db.query(Transaction).filter(
                Transaction.category_id.is_not(None)
            ).count()
            
            coverage_percentage = (categorized_transactions / total_transactions * 100) if total_transactions > 0 else 0
            
            return {
                "total_transactions": total_transactions,
                "categorized_transactions": categorized_transactions,
                "uncategorized_transactions": total_transactions - categorized_transactions,
                "coverage_percentage": round(coverage_percentage, 2)
            }
        
        except Exception as e:
            print(f"Error getting categorization stats: {e}")
            return {
                "total_transactions": 0,
                "categorized_transactions": 0,
                "uncategorized_transactions": 0,
                "coverage_percentage": 0
            }