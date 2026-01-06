"""
Search and Analytics Router

Provides endpoints for global search across all resources and
analytics/forecasting features.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from typing import List, Optional, Literal
from uuid import UUID
from datetime import date, datetime, timedelta
from pydantic import BaseModel

from app.database import get_async_session
from app.dependencies import get_current_active_user, verify_entity_access
from app.models.user import User
from app.models.transaction import Transaction
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.vendor import Vendor
from app.models.inventory import InventoryItem

router = APIRouter(
    prefix="/api/v1/{entity_id}",
    tags=["Search & Analytics"],
)


# ===========================================
# SEARCH SCHEMAS
# ===========================================

class SearchResult(BaseModel):
    """Individual search result."""
    id: str
    type: str
    title: str
    subtitle: Optional[str] = None
    url: str
    relevance_score: float = 1.0


class GlobalSearchResponse(BaseModel):
    """Response for global search."""
    query: str
    total_results: int
    results: List[SearchResult]
    by_type: dict


class AnalyticsSummary(BaseModel):
    """Summary analytics data."""
    period: str
    total_revenue: float
    total_expenses: float
    net_profit: float
    growth_rate: float
    transaction_count: int


class ForecastData(BaseModel):
    """Forecast data point."""
    date: date
    predicted_revenue: float
    predicted_expenses: float
    confidence_interval_low: float
    confidence_interval_high: float


class ForecastResponse(BaseModel):
    """Response for forecasting."""
    forecast_period: str
    data_points: List[ForecastData]
    methodology: str
    accuracy_score: float


# ===========================================
# GLOBAL SEARCH
# ===========================================

@router.get(
    "/search",
    response_model=GlobalSearchResponse,
    summary="Global search",
    description="Search across all resources (transactions, invoices, customers, vendors, inventory).",
)
async def global_search(
    entity_id: UUID,
    q: str = Query(..., min_length=2, description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated resource types to search"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results per type"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Perform a global search across all entity resources.
    
    Searchable types: transactions, invoices, customers, vendors, inventory
    """
    await verify_entity_access(entity_id, current_user, db)
    
    search_term = f"%{q.lower()}%"
    results = []
    by_type = {}
    
    # Determine which types to search
    type_filter = types.split(",") if types else ["transactions", "invoices", "customers", "vendors", "inventory"]
    
    # Search transactions
    if "transactions" in type_filter:
        query = select(Transaction).where(
            Transaction.entity_id == entity_id,
            or_(
                func.lower(Transaction.description).like(search_term),
                func.lower(Transaction.reference).like(search_term),
            )
        ).limit(limit)
        
        result = await db.execute(query)
        transactions = result.scalars().all()
        
        tx_results = []
        for tx in transactions:
            tx_results.append(SearchResult(
                id=str(tx.id),
                type="transaction",
                title=tx.description or "Transaction",
                subtitle=f"₦{tx.amount:,.2f} - {tx.transaction_date}",
                url=f"/transactions/{tx.id}",
            ))
        results.extend(tx_results)
        by_type["transactions"] = len(tx_results)
    
    # Search invoices
    if "invoices" in type_filter:
        query = select(Invoice).where(
            Invoice.entity_id == entity_id,
            or_(
                func.lower(Invoice.invoice_number).like(search_term),
                func.lower(Invoice.notes).like(search_term),
            )
        ).limit(limit)
        
        result = await db.execute(query)
        invoices = result.scalars().all()
        
        inv_results = []
        for inv in invoices:
            inv_results.append(SearchResult(
                id=str(inv.id),
                type="invoice",
                title=inv.invoice_number,
                subtitle=f"₦{inv.total_amount:,.2f} - {inv.status.value}",
                url=f"/invoices/{inv.id}",
            ))
        results.extend(inv_results)
        by_type["invoices"] = len(inv_results)
    
    # Search customers
    if "customers" in type_filter:
        query = select(Customer).where(
            Customer.entity_id == entity_id,
            or_(
                func.lower(Customer.name).like(search_term),
                func.lower(Customer.email).like(search_term),
                func.lower(Customer.phone).like(search_term),
            )
        ).limit(limit)
        
        result = await db.execute(query)
        customers = result.scalars().all()
        
        cust_results = []
        for c in customers:
            cust_results.append(SearchResult(
                id=str(c.id),
                type="customer",
                title=c.name,
                subtitle=c.email or c.phone,
                url=f"/customers/{c.id}",
            ))
        results.extend(cust_results)
        by_type["customers"] = len(cust_results)
    
    # Search vendors
    if "vendors" in type_filter:
        query = select(Vendor).where(
            Vendor.entity_id == entity_id,
            or_(
                func.lower(Vendor.name).like(search_term),
                func.lower(Vendor.email).like(search_term),
                func.lower(Vendor.tin).like(search_term),
            )
        ).limit(limit)
        
        result = await db.execute(query)
        vendors = result.scalars().all()
        
        vendor_results = []
        for v in vendors:
            vendor_results.append(SearchResult(
                id=str(v.id),
                type="vendor",
                title=v.name,
                subtitle=v.email or v.tin,
                url=f"/vendors/{v.id}",
            ))
        results.extend(vendor_results)
        by_type["vendors"] = len(vendor_results)
    
    # Search inventory
    if "inventory" in type_filter:
        query = select(InventoryItem).where(
            InventoryItem.entity_id == entity_id,
            or_(
                func.lower(InventoryItem.name).like(search_term),
                func.lower(InventoryItem.sku).like(search_term),
                func.lower(InventoryItem.description).like(search_term),
            )
        ).limit(limit)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        inv_results = []
        for item in items:
            inv_results.append(SearchResult(
                id=str(item.id),
                type="inventory",
                title=item.name,
                subtitle=f"SKU: {item.sku} - Qty: {item.quantity}",
                url=f"/inventory/{item.id}",
            ))
        results.extend(inv_results)
        by_type["inventory"] = len(inv_results)
    
    return GlobalSearchResponse(
        query=q,
        total_results=len(results),
        results=results,
        by_type=by_type,
    )


# ===========================================
# ANALYTICS
# ===========================================

@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummary,
    summary="Get analytics summary",
    description="Get summary analytics for the specified period.",
)
async def get_analytics_summary(
    entity_id: UUID,
    period: Literal["week", "month", "quarter", "year"] = Query("month", description="Analytics period"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get summary analytics."""
    await verify_entity_access(entity_id, current_user, db)
    
    # Calculate date range
    today = date.today()
    if period == "week":
        start_date = today - timedelta(days=7)
        prev_start = start_date - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
        prev_start = start_date - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
        prev_start = start_date - timedelta(days=90)
    else:  # year
        start_date = today - timedelta(days=365)
        prev_start = start_date - timedelta(days=365)
    
    # Get current period transactions
    from app.models.transaction import TransactionType
    
    # Revenue
    revenue_query = select(func.sum(Transaction.amount)).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_type == TransactionType.income,
    )
    result = await db.execute(revenue_query)
    total_revenue = float(result.scalar() or 0)
    
    # Expenses
    expense_query = select(func.sum(Transaction.amount)).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_type == TransactionType.expense,
    )
    result = await db.execute(expense_query)
    total_expenses = float(result.scalar() or 0)
    
    # Transaction count
    count_query = select(func.count(Transaction.id)).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
    )
    result = await db.execute(count_query)
    transaction_count = result.scalar() or 0
    
    # Previous period for growth calculation
    prev_revenue_query = select(func.sum(Transaction.amount)).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= prev_start,
        Transaction.transaction_date < start_date,
        Transaction.transaction_type == TransactionType.income,
    )
    result = await db.execute(prev_revenue_query)
    prev_revenue = float(result.scalar() or 0)
    
    # Calculate growth rate
    if prev_revenue > 0:
        growth_rate = ((total_revenue - prev_revenue) / prev_revenue) * 100
    else:
        growth_rate = 100.0 if total_revenue > 0 else 0.0
    
    return AnalyticsSummary(
        period=period,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=total_revenue - total_expenses,
        growth_rate=round(growth_rate, 2),
        transaction_count=transaction_count,
    )


@router.get(
    "/analytics/trends",
    summary="Get trend data",
    description="Get trend data for revenue, expenses over time.",
)
async def get_trends(
    entity_id: UUID,
    period: Literal["week", "month", "quarter", "year"] = Query("month", description="Trend period"),
    granularity: Literal["day", "week", "month"] = Query("day", description="Data granularity"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get trend data."""
    await verify_entity_access(entity_id, current_user, db)
    
    # Calculate date range
    today = date.today()
    if period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:
        start_date = today - timedelta(days=365)
    
    from app.models.transaction import TransactionType
    
    # Get all transactions in period
    query = select(Transaction).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
    ).order_by(Transaction.transaction_date)
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    # Group by date
    daily_data = {}
    for tx in transactions:
        key = tx.transaction_date.isoformat()
        if key not in daily_data:
            daily_data[key] = {"date": key, "revenue": 0, "expenses": 0}
        
        if tx.transaction_type == TransactionType.income:
            daily_data[key]["revenue"] += float(tx.amount)
        else:
            daily_data[key]["expenses"] += float(tx.amount)
    
    return {
        "period": period,
        "granularity": granularity,
        "start_date": start_date.isoformat(),
        "end_date": today.isoformat(),
        "data_points": list(daily_data.values()),
    }


@router.get(
    "/analytics/top-customers",
    summary="Get top customers",
    description="Get top customers by revenue.",
)
async def get_top_customers(
    entity_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Number of customers"),
    period: Literal["month", "quarter", "year", "all"] = Query("year", description="Period"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get top customers by revenue."""
    await verify_entity_access(entity_id, current_user, db)
    
    # Calculate date filter
    today = date.today()
    if period == "month":
        start_date = today - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    elif period == "year":
        start_date = today - timedelta(days=365)
    else:
        start_date = None
    
    # Query invoices grouped by customer
    query = select(
        Customer.id,
        Customer.name,
        Customer.email,
        func.sum(Invoice.total_amount).label("total_revenue"),
        func.count(Invoice.id).label("invoice_count"),
    ).join(Invoice, Customer.id == Invoice.customer_id).where(
        Customer.entity_id == entity_id,
    ).group_by(Customer.id, Customer.name, Customer.email).order_by(
        func.sum(Invoice.total_amount).desc()
    ).limit(limit)
    
    if start_date:
        query = query.where(Invoice.invoice_date >= start_date)
    
    result = await db.execute(query)
    top_customers = result.all()
    
    return {
        "period": period,
        "customers": [
            {
                "id": str(c.id),
                "name": c.name,
                "email": c.email,
                "total_revenue": float(c.total_revenue or 0),
                "invoice_count": c.invoice_count,
            }
            for c in top_customers
        ]
    }


@router.get(
    "/analytics/top-expenses",
    summary="Get top expense categories",
    description="Get top expense categories by amount.",
)
async def get_top_expenses(
    entity_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Number of categories"),
    period: Literal["month", "quarter", "year"] = Query("month", description="Period"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get top expense categories."""
    await verify_entity_access(entity_id, current_user, db)
    
    from app.models.transaction import TransactionType
    from app.models.category import Category
    
    today = date.today()
    if period == "month":
        start_date = today - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:
        start_date = today - timedelta(days=365)
    
    query = select(
        Category.id,
        Category.name,
        func.sum(Transaction.amount).label("total_amount"),
        func.count(Transaction.id).label("transaction_count"),
    ).join(Transaction, Category.id == Transaction.category_id).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_type == TransactionType.expense,
    ).group_by(Category.id, Category.name).order_by(
        func.sum(Transaction.amount).desc()
    ).limit(limit)
    
    result = await db.execute(query)
    categories = result.all()
    
    return {
        "period": period,
        "categories": [
            {
                "id": str(c.id),
                "name": c.name,
                "total_amount": float(c.total_amount or 0),
                "transaction_count": c.transaction_count,
            }
            for c in categories
        ]
    }


# ===========================================
# FORECASTING
# ===========================================

@router.get(
    "/analytics/forecast",
    response_model=ForecastResponse,
    summary="Get revenue/expense forecast",
    description="Get AI-powered forecast for future revenue and expenses.",
)
async def get_forecast(
    entity_id: UUID,
    forecast_months: int = Query(3, ge=1, le=12, description="Months to forecast"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get revenue/expense forecast."""
    await verify_entity_access(entity_id, current_user, db)
    
    # In a full implementation, this would use ML models
    # For now, use simple moving average
    
    from app.models.transaction import TransactionType
    
    # Get historical data (last 12 months)
    today = date.today()
    start_date = today - timedelta(days=365)
    
    # Calculate monthly averages
    revenue_query = select(func.avg(Transaction.amount)).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_type == TransactionType.income,
    )
    result = await db.execute(revenue_query)
    avg_revenue = float(result.scalar() or 0) * 30  # Approximate monthly
    
    expense_query = select(func.avg(Transaction.amount)).where(
        Transaction.entity_id == entity_id,
        Transaction.transaction_date >= start_date,
        Transaction.transaction_type == TransactionType.expense,
    )
    result = await db.execute(expense_query)
    avg_expense = float(result.scalar() or 0) * 30
    
    # Generate forecast data points
    forecast_points = []
    current_date = today
    for i in range(forecast_months):
        current_date = current_date + timedelta(days=30)
        
        # Add some variance to predictions
        variance = 0.1 * (i + 1)  # Increase uncertainty over time
        
        forecast_points.append(ForecastData(
            date=current_date,
            predicted_revenue=avg_revenue * (1 + 0.02 * i),  # Assume 2% monthly growth
            predicted_expenses=avg_expense,
            confidence_interval_low=avg_revenue * (1 - variance),
            confidence_interval_high=avg_revenue * (1 + variance),
        ))
    
    return ForecastResponse(
        forecast_period=f"{forecast_months} months",
        data_points=forecast_points,
        methodology="Simple Moving Average with Growth Assumption",
        accuracy_score=0.75,  # Placeholder
    )


@router.get(
    "/analytics/kpis",
    summary="Get key performance indicators",
    description="Get dashboard KPIs for the entity.",
)
async def get_kpis(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get key performance indicators."""
    await verify_entity_access(entity_id, current_user, db)
    
    from app.models.transaction import TransactionType
    
    today = date.today()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    # Current month metrics
    current_revenue = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.entity_id == entity_id,
            Transaction.transaction_date >= month_start,
            Transaction.transaction_type == TransactionType.income,
        )
    )
    current_revenue = float(current_revenue.scalar() or 0)
    
    current_expenses = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.entity_id == entity_id,
            Transaction.transaction_date >= month_start,
            Transaction.transaction_type == TransactionType.expense,
        )
    )
    current_expenses = float(current_expenses.scalar() or 0)
    
    # Outstanding invoices
    outstanding = await db.execute(
        select(func.sum(Invoice.balance_due)).where(
            Invoice.entity_id == entity_id,
            Invoice.status.notin_(["paid", "cancelled"]),
        )
    )
    outstanding = float(outstanding.scalar() or 0)
    
    # Overdue invoices
    overdue = await db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.entity_id == entity_id,
            Invoice.due_date < today,
            Invoice.status.notin_(["paid", "cancelled"]),
        )
    )
    overdue_count = overdue.scalar() or 0
    
    return {
        "current_month": {
            "revenue": current_revenue,
            "expenses": current_expenses,
            "net_income": current_revenue - current_expenses,
        },
        "receivables": {
            "outstanding": outstanding,
            "overdue_count": overdue_count,
        },
        "profit_margin": round((current_revenue - current_expenses) / current_revenue * 100, 2) if current_revenue > 0 else 0,
    }
