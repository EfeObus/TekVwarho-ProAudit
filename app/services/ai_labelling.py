"""
AI Transaction Labelling Service
Uses OpenAI GPT and ML models to predict G/L accounts and categories

Implements "Zero-Touch" Autonomous Accounting for Nigerian Tax Reform 2026
"""

import os
import json
import hashlib
import pickle
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


@dataclass
class TransactionPrediction:
    """Result of AI transaction prediction"""
    category_id: Optional[str]
    category_name: str
    gl_account_code: Optional[str]
    gl_account_name: str
    confidence_score: float
    reasoning: str
    tax_implications: Optional[Dict[str, Any]] = None
    suggested_dimensions: Optional[List[Dict[str, str]]] = None


@dataclass
class TrainingData:
    """Training data for ML model"""
    description: str
    amount: float
    category: str
    gl_account: str


class AITransactionLabeller:
    """
    AI-powered transaction labelling service
    Uses OpenAI for intelligent categorization and Scikit-learn for pattern matching
    """
    
    # Nigerian-specific vendor patterns for quick matching
    VENDOR_PATTERNS = {
        # Utilities
        "phcn": {"category": "Utilities: Electricity", "gl": "6100", "vat_applicable": True},
        "ekedc": {"category": "Utilities: Electricity", "gl": "6100", "vat_applicable": True},
        "ikedc": {"category": "Utilities: Electricity", "gl": "6100", "vat_applicable": True},
        "aedc": {"category": "Utilities: Electricity", "gl": "6100", "vat_applicable": True},
        "ibedc": {"category": "Utilities: Electricity", "gl": "6100", "vat_applicable": True},
        "mtn": {"category": "Utilities: Telecommunications", "gl": "6110", "vat_applicable": True},
        "glo": {"category": "Utilities: Telecommunications", "gl": "6110", "vat_applicable": True},
        "airtel": {"category": "Utilities: Telecommunications", "gl": "6110", "vat_applicable": True},
        "9mobile": {"category": "Utilities: Telecommunications", "gl": "6110", "vat_applicable": True},
        "dstv": {"category": "Utilities: Cable/Internet", "gl": "6115", "vat_applicable": True},
        "gotv": {"category": "Utilities: Cable/Internet", "gl": "6115", "vat_applicable": True},
        "startimes": {"category": "Utilities: Cable/Internet", "gl": "6115", "vat_applicable": True},
        
        # Banks
        "gtbank": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "gtb": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "zenith": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "access": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "uba": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "first bank": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "fcmb": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "stanbic": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "sterling": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "fidelity": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "wema": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "polaris": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "union bank": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "keystone": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        "ecobank": {"category": "Bank Charges", "gl": "6200", "vat_applicable": False},
        
        # Government/Taxes
        "firs": {"category": "Taxes: Federal", "gl": "2300", "vat_applicable": False},
        "lirs": {"category": "Taxes: State (Lagos)", "gl": "2310", "vat_applicable": False},
        "irs": {"category": "Taxes: State", "gl": "2310", "vat_applicable": False},
        "cac": {"category": "Registration Fees", "gl": "6300", "vat_applicable": False},
        "customs": {"category": "Import Duties", "gl": "5200", "vat_applicable": False},
        
        # Fuel/Transport
        "nnpc": {"category": "Vehicle: Fuel", "gl": "6400", "vat_applicable": True},
        "mobil": {"category": "Vehicle: Fuel", "gl": "6400", "vat_applicable": True},
        "total": {"category": "Vehicle: Fuel", "gl": "6400", "vat_applicable": True},
        "oando": {"category": "Vehicle: Fuel", "gl": "6400", "vat_applicable": True},
        "conoil": {"category": "Vehicle: Fuel", "gl": "6400", "vat_applicable": True},
        "ardova": {"category": "Vehicle: Fuel", "gl": "6400", "vat_applicable": True},
        
        # Office/Supplies
        "shoprite": {"category": "Office Supplies", "gl": "6500", "vat_applicable": True},
        "spar": {"category": "Office Supplies", "gl": "6500", "vat_applicable": True},
        "hubmart": {"category": "Office Supplies", "gl": "6500", "vat_applicable": True},
        "jumia": {"category": "Office Supplies", "gl": "6500", "vat_applicable": True},
        "konga": {"category": "Office Supplies", "gl": "6500", "vat_applicable": True},
        
        # Professional Services
        "lawyer": {"category": "Professional Fees: Legal", "gl": "6600", "vat_applicable": True, "wht_rate": 10},
        "solicitor": {"category": "Professional Fees: Legal", "gl": "6600", "vat_applicable": True, "wht_rate": 10},
        "accountant": {"category": "Professional Fees: Accounting", "gl": "6610", "vat_applicable": True, "wht_rate": 10},
        "audit": {"category": "Professional Fees: Audit", "gl": "6620", "vat_applicable": True, "wht_rate": 10},
        "consultant": {"category": "Professional Fees: Consulting", "gl": "6630", "vat_applicable": True, "wht_rate": 10},
        
        # Insurance
        "aiico": {"category": "Insurance", "gl": "6700", "vat_applicable": False},
        "leadway": {"category": "Insurance", "gl": "6700", "vat_applicable": False},
        "axa mansard": {"category": "Insurance", "gl": "6700", "vat_applicable": False},
        "custodian": {"category": "Insurance", "gl": "6700", "vat_applicable": False},
        "cornerstone": {"category": "Insurance", "gl": "6700", "vat_applicable": False},
        
        # Rent
        "rent": {"category": "Rent Expense", "gl": "6800", "vat_applicable": False, "wht_rate": 10},
        "lease": {"category": "Rent Expense", "gl": "6800", "vat_applicable": False, "wht_rate": 10},
    }
    
    # GL Account mapping for Nigerian Chart of Accounts
    GL_ACCOUNTS = {
        # Assets (1000-1999)
        "1000": "Cash and Cash Equivalents",
        "1100": "Bank Accounts",
        "1200": "Accounts Receivable",
        "1300": "Inventory",
        "1400": "Prepaid Expenses",
        "1500": "Fixed Assets",
        "1600": "Accumulated Depreciation",
        
        # Liabilities (2000-2999)
        "2000": "Accounts Payable",
        "2100": "Accrued Expenses",
        "2200": "VAT Payable",
        "2300": "Taxes Payable - Federal",
        "2310": "Taxes Payable - State",
        "2320": "PAYE Payable",
        "2330": "WHT Payable",
        "2400": "Pension Payable",
        "2500": "Long-term Liabilities",
        
        # Equity (3000-3999)
        "3000": "Share Capital",
        "3100": "Retained Earnings",
        "3200": "Current Year Earnings",
        
        # Revenue (4000-4999)
        "4000": "Sales Revenue",
        "4100": "Service Revenue",
        "4200": "Interest Income",
        "4300": "Other Income",
        
        # Cost of Sales (5000-5499)
        "5000": "Cost of Goods Sold",
        "5100": "Direct Labor",
        "5200": "Import Duties",
        "5300": "Freight and Shipping",
        
        # Operating Expenses (6000-6999)
        "6000": "Salaries and Wages",
        "6050": "Pension Contributions",
        "6100": "Utilities: Electricity",
        "6110": "Utilities: Telecommunications",
        "6115": "Utilities: Cable/Internet",
        "6120": "Utilities: Water",
        "6200": "Bank Charges",
        "6300": "Registration Fees",
        "6400": "Vehicle: Fuel",
        "6410": "Vehicle: Maintenance",
        "6500": "Office Supplies",
        "6600": "Professional Fees: Legal",
        "6610": "Professional Fees: Accounting",
        "6620": "Professional Fees: Audit",
        "6630": "Professional Fees: Consulting",
        "6700": "Insurance",
        "6800": "Rent Expense",
        "6900": "Depreciation Expense",
        "6950": "Miscellaneous Expense",
    }
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.confidence_threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.85"))
        self.ml_enabled = os.getenv("ML_GL_PREDICTION_ENABLED", "True").lower() == "true"
        self.ai_enabled = os.getenv("AI_TRANSACTION_LABELLING_ENABLED", "True").lower() == "true"
        
        # ML model cache
        self._ml_model = None
        self._vectorizer = None
        self._label_encoder = None
    
    async def predict_category(
        self,
        description: str,
        amount: Decimal,
        transaction_type: str = "expense",
        vendor_name: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> TransactionPrediction:
        """
        Predict the category and G/L account for a transaction
        
        Args:
            description: Transaction description/narration
            amount: Transaction amount
            transaction_type: 'income' or 'expense'
            vendor_name: Optional vendor/payee name
            additional_context: Additional context for prediction
            
        Returns:
            TransactionPrediction with category, GL account, and confidence score
        """
        
        # Step 1: Try pattern matching first (fastest)
        pattern_result = self._match_vendor_pattern(description, vendor_name)
        if pattern_result and pattern_result.confidence_score >= 0.90:
            return pattern_result
        
        # Step 2: Try ML model if available
        if self.ml_enabled:
            ml_result = await self._predict_with_ml(description, amount, transaction_type)
            if ml_result and ml_result.confidence_score >= self.confidence_threshold:
                return ml_result
        
        # Step 3: Use OpenAI for complex cases
        if self.ai_enabled and self.openai_api_key:
            ai_result = await self._predict_with_openai(
                description, amount, transaction_type, vendor_name, additional_context
            )
            if ai_result:
                return ai_result
        
        # Step 4: Return pattern match if available, otherwise uncategorized
        if pattern_result:
            return pattern_result
        
        return TransactionPrediction(
            category_id=None,
            category_name="Uncategorized",
            gl_account_code="6950",
            gl_account_name="Miscellaneous Expense",
            confidence_score=0.0,
            reasoning="Unable to determine category. Manual review required."
        )
    
    def _match_vendor_pattern(
        self,
        description: str,
        vendor_name: Optional[str] = None
    ) -> Optional[TransactionPrediction]:
        """Match against known vendor patterns"""
        
        search_text = f"{description} {vendor_name or ''}".lower()
        
        best_match = None
        best_score = 0.0
        
        for pattern, data in self.VENDOR_PATTERNS.items():
            if pattern in search_text:
                # Calculate match score based on pattern length and position
                score = len(pattern) / len(search_text) if search_text else 0
                score = min(score * 2, 0.95)  # Scale up but cap at 0.95
                
                if score > best_score:
                    best_score = score
                    
                    tax_implications = {}
                    if data.get("vat_applicable"):
                        tax_implications["vat_rate"] = 7.5
                    if data.get("wht_rate"):
                        tax_implications["wht_rate"] = data["wht_rate"]
                    
                    best_match = TransactionPrediction(
                        category_id=None,
                        category_name=data["category"],
                        gl_account_code=data["gl"],
                        gl_account_name=self.GL_ACCOUNTS.get(data["gl"], data["category"]),
                        confidence_score=score,
                        reasoning=f"Matched pattern: '{pattern}' in transaction description",
                        tax_implications=tax_implications if tax_implications else None
                    )
        
        return best_match
    
    async def _predict_with_ml(
        self,
        description: str,
        amount: Decimal,
        transaction_type: str
    ) -> Optional[TransactionPrediction]:
        """Use ML model for prediction"""
        
        try:
            # Load or train ML model
            if not self._ml_model:
                await self._load_or_train_ml_model()
            
            if not self._ml_model:
                return None
            
            # Vectorize the description
            features = self._vectorizer.transform([description.lower()])
            
            # Predict
            prediction = self._ml_model.predict(features)[0]
            probabilities = self._ml_model.predict_proba(features)[0]
            confidence = max(probabilities)
            
            # Decode the label
            category_name = self._label_encoder.inverse_transform([prediction])[0]
            
            # Get GL account
            gl_code = self._get_gl_for_category(category_name)
            
            return TransactionPrediction(
                category_id=None,
                category_name=category_name,
                gl_account_code=gl_code,
                gl_account_name=self.GL_ACCOUNTS.get(gl_code, category_name),
                confidence_score=float(confidence),
                reasoning=f"ML model prediction based on historical patterns"
            )
            
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return None
    
    async def _predict_with_openai(
        self,
        description: str,
        amount: Decimal,
        transaction_type: str,
        vendor_name: Optional[str],
        additional_context: Optional[Dict[str, Any]]
    ) -> Optional[TransactionPrediction]:
        """Use OpenAI for intelligent prediction"""
        
        try:
            import openai
            
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)
            
            prompt = f"""You are an expert Nigerian accountant familiar with the 2026 Tax Reform.
Analyze this transaction and suggest the appropriate category and G/L account.

Transaction Details:
- Description: {description}
- Amount: NGN {amount:,.2f}
- Type: {transaction_type}
- Vendor/Payee: {vendor_name or 'Unknown'}
{f'- Additional Context: {json.dumps(additional_context)}' if additional_context else ''}

Available G/L Accounts:
{json.dumps(self.GL_ACCOUNTS, indent=2)}

Respond in JSON format:
{{
    "category_name": "Category Name",
    "gl_account_code": "XXXX",
    "confidence_score": 0.0 to 1.0,
    "reasoning": "Brief explanation",
    "tax_implications": {{
        "vat_applicable": true/false,
        "vat_rate": 7.5 or null,
        "wht_applicable": true/false,
        "wht_rate": rate or null,
        "wht_type": "professional/contract/rent/etc" or null
    }},
    "suggested_dimensions": [
        {{"type": "department", "value": "suggested value"}},
        {{"type": "project", "value": "suggested value"}}
    ]
}}"""
            
            response = await client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are a Nigerian tax and accounting expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content
            
            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            result = json.loads(result_text.strip())
            
            return TransactionPrediction(
                category_id=None,
                category_name=result.get("category_name", "Uncategorized"),
                gl_account_code=result.get("gl_account_code"),
                gl_account_name=self.GL_ACCOUNTS.get(
                    result.get("gl_account_code"), 
                    result.get("category_name", "Unknown")
                ),
                confidence_score=float(result.get("confidence_score", 0.7)),
                reasoning=result.get("reasoning", "AI prediction"),
                tax_implications=result.get("tax_implications"),
                suggested_dimensions=result.get("suggested_dimensions")
            )
            
        except Exception as e:
            logger.error(f"OpenAI prediction failed: {e}")
            return None
    
    async def _load_or_train_ml_model(self):
        """Load existing ML model or train a new one"""
        
        model_path = "ml_models/transaction_classifier.pkl"
        
        try:
            # Try to load existing model
            if os.path.exists(model_path):
                with open(model_path, "rb") as f:
                    model_data = pickle.load(f)
                    self._ml_model = model_data["model"]
                    self._vectorizer = model_data["vectorizer"]
                    self._label_encoder = model_data["label_encoder"]
                    logger.info("Loaded existing ML model")
                    return
        except Exception as e:
            logger.warning(f"Failed to load ML model: {e}")
        
        # Train new model with default data if needed
        await self._train_ml_model_with_defaults()
    
    async def _train_ml_model_with_defaults(self):
        """Train ML model with default Nigerian transaction patterns"""
        
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.naive_bayes import MultinomialNB
            from sklearn.preprocessing import LabelEncoder
            
            # Default training data based on Nigerian patterns
            training_data = [
                ("phcn electricity bill payment", "Utilities: Electricity"),
                ("ekedc prepaid meter recharge", "Utilities: Electricity"),
                ("mtn airtime purchase", "Utilities: Telecommunications"),
                ("glo data subscription", "Utilities: Telecommunications"),
                ("dstv subscription renewal", "Utilities: Cable/Internet"),
                ("bank charges transfer fee", "Bank Charges"),
                ("stamp duty charge", "Bank Charges"),
                ("sms alert fee", "Bank Charges"),
                ("fuel purchase filling station", "Vehicle: Fuel"),
                ("diesel for generator", "Vehicle: Fuel"),
                ("office stationery purchase", "Office Supplies"),
                ("printer cartridge", "Office Supplies"),
                ("legal fees lawyer payment", "Professional Fees: Legal"),
                ("audit fee annual audit", "Professional Fees: Audit"),
                ("consulting fee consultant", "Professional Fees: Consulting"),
                ("accounting services", "Professional Fees: Accounting"),
                ("office rent payment monthly", "Rent Expense"),
                ("warehouse lease", "Rent Expense"),
                ("insurance premium payment", "Insurance"),
                ("vehicle insurance renewal", "Insurance"),
                ("staff salary payment", "Salaries and Wages"),
                ("pension contribution remittance", "Pension Contributions"),
                ("firs vat payment", "Taxes: Federal"),
                ("paye tax remittance", "Taxes: State"),
                ("sales revenue customer payment", "Sales Revenue"),
                ("service fee income", "Service Revenue"),
                ("import duty customs payment", "Import Duties"),
                ("shipping freight cost", "Cost of Goods Sold"),
            ]
            
            descriptions = [d[0] for d in training_data]
            categories = [d[1] for d in training_data]
            
            # Vectorize descriptions
            self._vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words='english',
                ngram_range=(1, 2),
                max_features=500
            )
            X = self._vectorizer.fit_transform(descriptions)
            
            # Encode labels
            self._label_encoder = LabelEncoder()
            y = self._label_encoder.fit_transform(categories)
            
            # Train classifier
            self._ml_model = MultinomialNB(alpha=0.1)
            self._ml_model.fit(X, y)
            
            # Save model
            os.makedirs("ml_models", exist_ok=True)
            with open("ml_models/transaction_classifier.pkl", "wb") as f:
                pickle.dump({
                    "model": self._ml_model,
                    "vectorizer": self._vectorizer,
                    "label_encoder": self._label_encoder
                }, f)
            
            logger.info("Trained and saved new ML model")
            
        except ImportError:
            logger.warning("scikit-learn not installed, ML predictions disabled")
            self.ml_enabled = False
        except Exception as e:
            logger.error(f"Failed to train ML model: {e}")
    
    async def train_from_historical_data(
        self,
        db: AsyncSession,
        entity_id: str,
        min_samples: int = 50
    ):
        """Train ML model from historical transaction data"""
        
        from app.models.transaction import Transaction
        from app.models.category import Category
        
        # Fetch historical transactions with categories
        query = select(Transaction, Category).join(
            Category, Transaction.category_id == Category.id
        ).where(
            Transaction.entity_id == entity_id,
            Transaction.category_id.isnot(None)
        ).limit(10000)
        
        result = await db.execute(query)
        rows = result.all()
        
        if len(rows) < min_samples:
            logger.warning(f"Insufficient training data: {len(rows)} samples (need {min_samples})")
            return False
        
        descriptions = [row[0].description or "" for row in rows]
        categories = [row[1].name for row in rows]
        
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.naive_bayes import MultinomialNB
            from sklearn.preprocessing import LabelEncoder
            
            self._vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words='english',
                ngram_range=(1, 2),
                max_features=1000
            )
            X = self._vectorizer.fit_transform(descriptions)
            
            self._label_encoder = LabelEncoder()
            y = self._label_encoder.fit_transform(categories)
            
            self._ml_model = MultinomialNB(alpha=0.1)
            self._ml_model.fit(X, y)
            
            # Save entity-specific model
            model_path = f"ml_models/transaction_classifier_{entity_id}.pkl"
            os.makedirs("ml_models", exist_ok=True)
            with open(model_path, "wb") as f:
                pickle.dump({
                    "model": self._ml_model,
                    "vectorizer": self._vectorizer,
                    "label_encoder": self._label_encoder,
                    "trained_at": datetime.utcnow().isoformat(),
                    "sample_count": len(rows)
                }, f)
            
            logger.info(f"Trained custom ML model for entity {entity_id} with {len(rows)} samples")
            return True
            
        except Exception as e:
            logger.error(f"Failed to train from historical data: {e}")
            return False
    
    def _get_gl_for_category(self, category_name: str) -> str:
        """Get GL account code for a category name"""
        
        category_lower = category_name.lower()
        
        for pattern, data in self.VENDOR_PATTERNS.items():
            if data["category"].lower() == category_lower:
                return data["gl"]
        
        # Default mappings
        if "salary" in category_lower or "wage" in category_lower:
            return "6000"
        elif "electricity" in category_lower:
            return "6100"
        elif "telecom" in category_lower or "phone" in category_lower:
            return "6110"
        elif "bank" in category_lower:
            return "6200"
        elif "fuel" in category_lower:
            return "6400"
        elif "office" in category_lower or "supplies" in category_lower:
            return "6500"
        elif "legal" in category_lower:
            return "6600"
        elif "account" in category_lower:
            return "6610"
        elif "audit" in category_lower:
            return "6620"
        elif "consult" in category_lower:
            return "6630"
        elif "insurance" in category_lower:
            return "6700"
        elif "rent" in category_lower:
            return "6800"
        elif "sales" in category_lower or "revenue" in category_lower:
            return "4000"
        elif "service" in category_lower:
            return "4100"
        
        return "6950"  # Miscellaneous


# Singleton instance
ai_transaction_labeller = AITransactionLabeller()
