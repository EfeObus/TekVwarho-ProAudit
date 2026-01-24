"""
Mock Paystack Server for E2E Testing (#52)

This module provides a configurable mock Paystack server using the respx library
for comprehensive E2E testing of payment flows without hitting the real API.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
from dataclasses import dataclass, field

import httpx
import respx
from respx import MockRouter


# =============================================================================
# RESPONSE FACTORIES
# =============================================================================

@dataclass
class PaystackCustomer:
    """Represents a Paystack customer."""
    id: int
    email: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    customer_code: str = ""
    authorizations: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.customer_code:
            self.customer_code = f"CUS_{uuid4().hex[:12]}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "customer_code": self.customer_code,
            "authorizations": self.authorizations,
        }


@dataclass
class PaystackTransaction:
    """Represents a Paystack transaction."""
    id: int
    reference: str
    amount: int  # In kobo
    status: str = "success"
    currency: str = "NGN"
    channel: str = "card"
    gateway_response: str = "Successful"
    authorization: Optional[Dict] = None
    customer: Optional[PaystackCustomer] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "reference": self.reference,
            "amount": self.amount,
            "status": self.status,
            "currency": self.currency,
            "channel": self.channel,
            "gateway_response": self.gateway_response,
            "paid_at": datetime.utcnow().isoformat() if self.status == "success" else None,
            "created_at": datetime.utcnow().isoformat(),
            "authorization": self.authorization or self._default_authorization(),
            "customer": self.customer.to_dict() if self.customer else None,
            "metadata": self.metadata,
        }
    
    def _default_authorization(self) -> Dict:
        return {
            "authorization_code": f"AUTH_{uuid4().hex[:12]}",
            "bin": "408408",
            "last4": "4081",
            "exp_month": "12",
            "exp_year": "2025",
            "channel": "card",
            "card_type": "visa",
            "bank": "Test Bank",
            "country_code": "NG",
            "brand": "visa",
            "reusable": True,
            "signature": f"SIG_{uuid4().hex[:12]}",
        }


@dataclass
class PaystackSubscription:
    """Represents a Paystack subscription."""
    id: int
    subscription_code: str
    email_token: str
    amount: int
    status: str = "active"
    cron_expression: str = "0 0 1 * *"
    next_payment_date: Optional[datetime] = None
    plan: Optional[Dict] = None
    authorization: Optional[Dict] = None
    customer: Optional[PaystackCustomer] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subscription_code": self.subscription_code,
            "email_token": self.email_token,
            "amount": self.amount,
            "status": self.status,
            "cron_expression": self.cron_expression,
            "next_payment_date": (self.next_payment_date or datetime.utcnow() + timedelta(days=30)).isoformat(),
            "plan": self.plan or {},
            "authorization": self.authorization or {},
            "customer": self.customer.to_dict() if self.customer else {},
        }


# =============================================================================
# MOCK PAYSTACK SERVER
# =============================================================================

class MockPaystackServer:
    """
    Configurable mock Paystack server for E2E testing.
    
    Usage:
        mock_paystack = MockPaystackServer()
        
        with mock_paystack.activate():
            # Your test code that calls Paystack API
            response = await client.post("/api/billing/initialize", ...)
        
        # Configure specific behaviors
        mock_paystack.set_verification_response(status="failed", message="Insufficient Funds")
        
        # Add customers
        customer = mock_paystack.create_customer("test@example.com")
        
        # Simulate webhook
        webhook_payload = mock_paystack.generate_webhook_payload("charge.success", transaction)
    """
    
    BASE_URL = "https://api.paystack.co"
    
    def __init__(self, secret_key: str = "sk_test_xxx"):
        self.secret_key = secret_key
        self.webhook_secret = "test_webhook_secret"
        self.customers: Dict[str, PaystackCustomer] = {}
        self.transactions: Dict[str, PaystackTransaction] = {}
        self.subscriptions: Dict[str, PaystackSubscription] = {}
        self._id_counter = 1000000
        
        # Configurable responses
        self._verification_response: Optional[Dict] = None
        self._initialization_response: Optional[Dict] = None
        self._charge_response: Optional[Dict] = None
        self._should_fail_verification = False
        self._should_fail_initialization = False
        self._custom_error: Optional[Dict] = None
        
        self._router: Optional[MockRouter] = None
    
    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter
    
    # ===========================================
    # Customer Management
    # ===========================================
    
    def create_customer(
        self,
        email: str,
        first_name: str = "Test",
        last_name: str = "User",
        phone: str = "+2348012345678",
    ) -> PaystackCustomer:
        """Create a customer in the mock server."""
        customer = PaystackCustomer(
            id=self._next_id(),
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )
        self.customers[customer.customer_code] = customer
        self.customers[email] = customer
        return customer
    
    def add_authorization_to_customer(
        self,
        customer: PaystackCustomer,
        card_type: str = "visa",
        last4: str = "4081",
        exp_month: str = "12",
        exp_year: str = "2025",
        reusable: bool = True,
    ) -> Dict:
        """Add a saved card authorization to a customer."""
        auth = {
            "authorization_code": f"AUTH_{uuid4().hex[:12]}",
            "bin": "408408",
            "last4": last4,
            "exp_month": exp_month,
            "exp_year": exp_year,
            "channel": "card",
            "card_type": card_type,
            "bank": "Test Bank",
            "country_code": "NG",
            "brand": card_type,
            "reusable": reusable,
            "signature": f"SIG_{uuid4().hex[:12]}",
        }
        customer.authorizations.append(auth)
        return auth
    
    # ===========================================
    # Transaction Management
    # ===========================================
    
    def create_transaction(
        self,
        reference: str,
        amount: int,
        customer: Optional[PaystackCustomer] = None,
        status: str = "success",
        metadata: Optional[Dict] = None,
    ) -> PaystackTransaction:
        """Create a transaction in the mock server."""
        txn = PaystackTransaction(
            id=self._next_id(),
            reference=reference,
            amount=amount,
            status=status,
            customer=customer,
            metadata=metadata or {},
        )
        self.transactions[reference] = txn
        return txn
    
    # ===========================================
    # Response Configuration
    # ===========================================
    
    def set_verification_response(
        self,
        status: str = "success",
        gateway_response: str = "Successful",
        amount: Optional[int] = None,
    ):
        """Configure the verify transaction response."""
        self._verification_response = {
            "status": status,
            "gateway_response": gateway_response,
            "amount": amount,
        }
    
    def set_verification_failure(
        self,
        message: str = "Transaction failed",
        gateway_response: str = "Insufficient Funds",
    ):
        """Configure verification to fail."""
        self._should_fail_verification = True
        self._verification_response = {
            "status": "failed",
            "gateway_response": gateway_response,
            "message": message,
        }
    
    def set_initialization_response(
        self,
        authorization_url: str = "https://checkout.paystack.com/test",
        access_code: str = None,
        reference: str = None,
    ):
        """Configure the initialize transaction response."""
        self._initialization_response = {
            "authorization_url": authorization_url,
            "access_code": access_code or f"ACC_{uuid4().hex[:12]}",
            "reference": reference or f"TRX_{uuid4().hex[:12].upper()}",
        }
    
    def set_initialization_failure(self, message: str = "Initialization failed"):
        """Configure initialization to fail."""
        self._should_fail_initialization = True
        self._custom_error = {
            "status": False,
            "message": message,
        }
    
    def reset(self):
        """Reset all configurations to defaults."""
        self._verification_response = None
        self._initialization_response = None
        self._charge_response = None
        self._should_fail_verification = False
        self._should_fail_initialization = False
        self._custom_error = None
    
    # ===========================================
    # Webhook Generation
    # ===========================================
    
    def generate_webhook_payload(
        self,
        event: str,
        data: Any,
    ) -> Dict[str, Any]:
        """Generate a webhook payload for testing."""
        if isinstance(data, PaystackTransaction):
            data_dict = data.to_dict()
        elif isinstance(data, PaystackSubscription):
            data_dict = data.to_dict()
        elif isinstance(data, dict):
            data_dict = data
        else:
            data_dict = {}
        
        return {
            "event": event,
            "data": data_dict,
        }
    
    def sign_webhook_payload(self, payload: Dict) -> str:
        """Sign a webhook payload with HMAC-SHA512."""
        payload_bytes = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()
        return signature
    
    # ===========================================
    # Mock Router Setup
    # ===========================================
    
    def activate(self) -> MockRouter:
        """Activate the mock server and return the router."""
        self._router = respx.mock(base_url=self.BASE_URL)
        self._setup_routes()
        return self._router
    
    def _setup_routes(self):
        """Set up all mock routes."""
        if not self._router:
            return
        
        # Initialize transaction
        self._router.post("/transaction/initialize").mock(
            side_effect=self._handle_initialize
        )
        
        # Verify transaction
        self._router.get(path__regex=r"/transaction/verify/.*").mock(
            side_effect=self._handle_verify
        )
        
        # Get customer
        self._router.get(path__regex=r"/customer/.*").mock(
            side_effect=self._handle_get_customer
        )
        
        # Create customer
        self._router.post("/customer").mock(
            side_effect=self._handle_create_customer
        )
        
        # Create subscription
        self._router.post("/subscription").mock(
            side_effect=self._handle_create_subscription
        )
        
        # Disable subscription
        self._router.post("/subscription/disable").mock(
            side_effect=self._handle_disable_subscription
        )
        
        # Charge authorization
        self._router.post("/transaction/charge_authorization").mock(
            side_effect=self._handle_charge_authorization
        )
        
        # Plans
        self._router.get("/plan").mock(
            side_effect=self._handle_list_plans
        )
        self._router.post("/plan").mock(
            side_effect=self._handle_create_plan
        )
        
        # Refund
        self._router.post("/refund").mock(
            side_effect=self._handle_refund
        )
    
    def _handle_initialize(self, request: httpx.Request) -> httpx.Response:
        """Handle transaction initialization."""
        if self._should_fail_initialization and self._custom_error:
            return httpx.Response(400, json=self._custom_error)
        
        body = json.loads(request.content)
        email = body.get("email", "test@example.com")
        amount = body.get("amount", 0)
        reference = body.get("reference") or f"TRX_{uuid4().hex[:12].upper()}"
        
        if self._initialization_response:
            data = self._initialization_response.copy()
            data["reference"] = data.get("reference") or reference
        else:
            data = {
                "authorization_url": f"https://checkout.paystack.com/{uuid4().hex[:12]}",
                "access_code": f"ACC_{uuid4().hex[:12]}",
                "reference": reference,
            }
        
        # Create transaction record
        customer = self.customers.get(email)
        if not customer:
            customer = self.create_customer(email)
        
        self.create_transaction(
            reference=reference,
            amount=amount,
            customer=customer,
            status="pending",
            metadata=body.get("metadata", {}),
        )
        
        return httpx.Response(200, json={
            "status": True,
            "message": "Authorization URL created",
            "data": data,
        })
    
    def _handle_verify(self, request: httpx.Request) -> httpx.Response:
        """Handle transaction verification."""
        # Extract reference from URL path
        path = str(request.url.path)
        reference = path.split("/")[-1]
        
        if self._should_fail_verification:
            return httpx.Response(200, json={
                "status": True,
                "message": "Verification successful",
                "data": {
                    "status": "failed",
                    "reference": reference,
                    "amount": 0,
                    "gateway_response": self._verification_response.get("gateway_response", "Failed"),
                },
            })
        
        txn = self.transactions.get(reference)
        if txn:
            if self._verification_response:
                txn.status = self._verification_response.get("status", "success")
                txn.gateway_response = self._verification_response.get("gateway_response", "Successful")
                if self._verification_response.get("amount"):
                    txn.amount = self._verification_response["amount"]
            else:
                txn.status = "success"
            
            return httpx.Response(200, json={
                "status": True,
                "message": "Verification successful",
                "data": txn.to_dict(),
            })
        
        return httpx.Response(404, json={
            "status": False,
            "message": "Transaction not found",
        })
    
    def _handle_get_customer(self, request: httpx.Request) -> httpx.Response:
        """Handle get customer by email or code."""
        path = str(request.url.path)
        identifier = path.split("/")[-1]
        
        customer = self.customers.get(identifier)
        if customer:
            return httpx.Response(200, json={
                "status": True,
                "message": "Customer retrieved",
                "data": customer.to_dict(),
            })
        
        return httpx.Response(404, json={
            "status": False,
            "message": "Customer not found",
        })
    
    def _handle_create_customer(self, request: httpx.Request) -> httpx.Response:
        """Handle customer creation."""
        body = json.loads(request.content)
        
        customer = self.create_customer(
            email=body.get("email"),
            first_name=body.get("first_name", ""),
            last_name=body.get("last_name", ""),
            phone=body.get("phone", ""),
        )
        
        return httpx.Response(200, json={
            "status": True,
            "message": "Customer created",
            "data": customer.to_dict(),
        })
    
    def _handle_create_subscription(self, request: httpx.Request) -> httpx.Response:
        """Handle subscription creation."""
        body = json.loads(request.content)
        
        subscription = PaystackSubscription(
            id=self._next_id(),
            subscription_code=f"SUB_{uuid4().hex[:12]}",
            email_token=f"TOKEN_{uuid4().hex[:8]}",
            amount=body.get("amount", 0),
        )
        self.subscriptions[subscription.subscription_code] = subscription
        
        return httpx.Response(200, json={
            "status": True,
            "message": "Subscription created successfully",
            "data": subscription.to_dict(),
        })
    
    def _handle_disable_subscription(self, request: httpx.Request) -> httpx.Response:
        """Handle subscription disabling (cancellation)."""
        body = json.loads(request.content)
        code = body.get("code")
        
        if code in self.subscriptions:
            self.subscriptions[code].status = "cancelled"
            return httpx.Response(200, json={
                "status": True,
                "message": "Subscription disabled successfully",
            })
        
        return httpx.Response(404, json={
            "status": False,
            "message": "Subscription not found",
        })
    
    def _handle_charge_authorization(self, request: httpx.Request) -> httpx.Response:
        """Handle charging a saved card."""
        body = json.loads(request.content)
        
        reference = body.get("reference") or f"TRX_{uuid4().hex[:12].upper()}"
        
        if self._charge_response:
            txn = PaystackTransaction(
                id=self._next_id(),
                reference=reference,
                amount=body.get("amount", 0),
                status=self._charge_response.get("status", "success"),
                gateway_response=self._charge_response.get("gateway_response", "Successful"),
            )
        else:
            txn = PaystackTransaction(
                id=self._next_id(),
                reference=reference,
                amount=body.get("amount", 0),
                status="success",
            )
        
        self.transactions[reference] = txn
        
        return httpx.Response(200, json={
            "status": True,
            "message": "Charge attempted",
            "data": txn.to_dict(),
        })
    
    def _handle_list_plans(self, request: httpx.Request) -> httpx.Response:
        """Handle listing plans."""
        return httpx.Response(200, json={
            "status": True,
            "message": "Plans retrieved",
            "data": [
                {
                    "id": 1001,
                    "name": "Core Monthly",
                    "plan_code": "PLN_core_monthly",
                    "amount": 1000000,
                    "interval": "monthly",
                    "currency": "NGN",
                },
                {
                    "id": 1002,
                    "name": "Professional Monthly",
                    "plan_code": "PLN_professional_monthly",
                    "amount": 2500000,
                    "interval": "monthly",
                    "currency": "NGN",
                },
                {
                    "id": 1003,
                    "name": "Enterprise Monthly",
                    "plan_code": "PLN_enterprise_monthly",
                    "amount": 7500000,
                    "interval": "monthly",
                    "currency": "NGN",
                },
            ],
            "meta": {"total": 3, "page": 1, "perPage": 50},
        })
    
    def _handle_create_plan(self, request: httpx.Request) -> httpx.Response:
        """Handle plan creation."""
        body = json.loads(request.content)
        
        plan = {
            "id": self._next_id(),
            "name": body.get("name"),
            "plan_code": f"PLN_{uuid4().hex[:12]}",
            "amount": body.get("amount"),
            "interval": body.get("interval", "monthly"),
            "currency": body.get("currency", "NGN"),
        }
        
        return httpx.Response(200, json={
            "status": True,
            "message": "Plan created",
            "data": plan,
        })
    
    def _handle_refund(self, request: httpx.Request) -> httpx.Response:
        """Handle refund creation."""
        body = json.loads(request.content)
        
        refund = {
            "id": self._next_id(),
            "transaction": body.get("transaction"),
            "amount": body.get("amount"),
            "status": "processed",
            "currency": "NGN",
            "merchant_note": body.get("merchant_note", ""),
        }
        
        return httpx.Response(200, json={
            "status": True,
            "message": "Refund has been queued for processing",
            "data": refund,
        })


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_mock_paystack() -> MockPaystackServer:
    """Create a new MockPaystackServer instance."""
    return MockPaystackServer()


def mock_successful_payment(
    mock_server: MockPaystackServer,
    email: str,
    amount: int,
    organization_id: str,
) -> PaystackTransaction:
    """Create a successful payment scenario in the mock."""
    customer = mock_server.create_customer(email)
    mock_server.add_authorization_to_customer(customer)
    
    reference = f"TRX_{uuid4().hex[:12].upper()}"
    txn = mock_server.create_transaction(
        reference=reference,
        amount=amount,
        customer=customer,
        status="success",
        metadata={
            "organization_id": organization_id,
            "tier": "PROFESSIONAL",
            "billing_cycle": "monthly",
        },
    )
    
    return txn


def mock_failed_payment(
    mock_server: MockPaystackServer,
    email: str,
    amount: int,
    failure_reason: str = "Insufficient Funds",
) -> PaystackTransaction:
    """Create a failed payment scenario in the mock."""
    customer = mock_server.create_customer(email)
    
    reference = f"TRX_{uuid4().hex[:12].upper()}"
    txn = mock_server.create_transaction(
        reference=reference,
        amount=amount,
        customer=customer,
        status="failed",
        metadata={},
    )
    txn.gateway_response = failure_reason
    
    mock_server.set_verification_failure(
        message="Payment failed",
        gateway_response=failure_reason,
    )
    
    return txn
