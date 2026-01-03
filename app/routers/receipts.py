"""
TekVwarho ProAudit - Receipts Router

API endpoints for receipt upload, OCR processing, and document management.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from io import BytesIO

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.services.entity_service import EntityService
from app.services.ocr_service import OCRService, ExtractedReceiptData
from app.services.file_storage_service import FileStorageService, FileCategory
from app.schemas.auth import MessageResponse


router = APIRouter()


# ===========================================
# SCHEMAS
# ===========================================

class ReceiptUploadResponse(BaseModel):
    """Response after receipt upload."""
    file_id: str
    url: str
    filename: str
    content_type: str
    size: int
    extracted_data: Optional[dict] = None


class ExtractedDataResponse(BaseModel):
    """Extracted receipt data response."""
    vendor_name: Optional[str]
    vendor_address: Optional[str]
    vendor_tin: Optional[str]
    receipt_number: Optional[str]
    transaction_date: Optional[str]
    subtotal: Optional[float]
    vat_amount: Optional[float]
    total_amount: Optional[float]
    currency: str
    payment_method: Optional[str]
    line_items: Optional[List[dict]]
    confidence_score: float
    provider: str


class FileInfoResponse(BaseModel):
    """File information response."""
    file_id: str
    url: str
    filename: Optional[str]
    content_type: Optional[str]
    size: int
    created_at: Optional[str]
    category: Optional[str]


class CreateTransactionFromReceiptRequest(BaseModel):
    """Request to create transaction from receipt data."""
    file_id: str
    vendor_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    amount: float = Field(..., gt=0)
    vat_amount: Optional[float] = Field(0, ge=0)
    transaction_date: date
    notes: Optional[str] = None


# ===========================================
# HELPER FUNCTIONS
# ===========================================

async def verify_entity_access(
    entity_id: UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """Verify user has access to the entity."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id)
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business entity not found",
        )
    
    has_access = any(
        access.entity_id == entity_id 
        for access in user.entity_access
    )
    
    if not has_access and entity.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this business entity",
        )


# ===========================================
# RECEIPT UPLOAD ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/receipts/upload",
    response_model=ReceiptUploadResponse,
    summary="Upload receipt with OCR",
)
async def upload_receipt(
    entity_id: UUID,
    file: UploadFile = File(...),
    process_ocr: bool = Query(True, description="Process with OCR"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Upload a receipt image for OCR processing.
    
    Supported formats: JPEG, PNG, PDF
    
    Returns the uploaded file info and extracted data (if OCR enabled).
    """
    await verify_entity_access(entity_id, current_user, db)
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {allowed_types}",
        )
    
    # Read file content
    file_content = await file.read()
    
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB",
        )
    
    # Upload file to storage
    storage_service = FileStorageService()
    upload_result = await storage_service.upload_file(
        entity_id=entity_id,
        file_content=file_content,
        filename=file.filename or "receipt",
        content_type=file.content_type,
        category=FileCategory.RECEIPT,
        metadata={
            "uploaded_by": str(current_user.id),
            "original_filename": file.filename,
        },
    )
    
    # Process OCR if enabled
    extracted_data = None
    if process_ocr:
        ocr_service = OCRService()
        receipt_data = await ocr_service.process_receipt(
            file_content=file_content,
            filename=file.filename or "receipt",
            content_type=file.content_type,
        )
        extracted_data = receipt_data.to_dict()
    
    return ReceiptUploadResponse(
        file_id=upload_result["file_id"],
        url=upload_result["url"],
        filename=upload_result["filename"],
        content_type=upload_result["content_type"],
        size=upload_result["size"],
        extracted_data=extracted_data,
    )


@router.post(
    "/{entity_id}/receipts/{file_id}/reprocess",
    response_model=ExtractedDataResponse,
    summary="Reprocess receipt OCR",
)
async def reprocess_receipt_ocr(
    entity_id: UUID,
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Reprocess an existing receipt with OCR.
    
    Useful if initial processing failed or to get updated extraction.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    storage_service = FileStorageService()
    
    try:
        file_content, content_type = await storage_service.download_file(file_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt file not found",
        )
    
    ocr_service = OCRService()
    receipt_data = await ocr_service.process_receipt(
        file_content=file_content,
        filename=file_id,
        content_type=content_type,
    )
    
    return ExtractedDataResponse(
        vendor_name=receipt_data.vendor_name,
        vendor_address=receipt_data.vendor_address,
        vendor_tin=receipt_data.vendor_tin,
        receipt_number=receipt_data.receipt_number,
        transaction_date=receipt_data.transaction_date.isoformat() if receipt_data.transaction_date else None,
        subtotal=receipt_data.subtotal,
        vat_amount=receipt_data.vat_amount,
        total_amount=receipt_data.total_amount,
        currency=receipt_data.currency,
        payment_method=receipt_data.payment_method,
        line_items=[
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "amount": item.amount,
            }
            for item in (receipt_data.line_items or [])
        ],
        confidence_score=receipt_data.confidence_score,
        provider=receipt_data.provider,
    )


@router.post(
    "/{entity_id}/receipts/{file_id}/create-transaction",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction from receipt",
)
async def create_transaction_from_receipt(
    entity_id: UUID,
    file_id: str,
    request: CreateTransactionFromReceiptRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a transaction from receipt data.
    
    The receipt file will be attached to the transaction.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.transaction_service import TransactionService
    from app.models.transaction import TransactionType
    
    transaction_service = TransactionService(db)
    
    transaction = await transaction_service.create_transaction(
        entity_id=entity_id,
        transaction_type=TransactionType.EXPENSE,
        amount=request.amount,
        vat_amount=request.vat_amount,
        description=request.description or "Receipt expense",
        transaction_date=request.transaction_date,
        vendor_id=request.vendor_id,
        category_id=request.category_id,
        notes=request.notes,
        receipt_url=file_id,
        created_by=current_user.id,
    )
    
    return {
        "message": "Transaction created successfully",
        "transaction_id": str(transaction.id),
        "receipt_file_id": file_id,
    }


# ===========================================
# FILE MANAGEMENT ENDPOINTS
# ===========================================

@router.get(
    "/{entity_id}/files",
    response_model=List[FileInfoResponse],
    summary="List files",
)
async def list_files(
    entity_id: UUID,
    category: Optional[str] = Query(None, description="File category filter"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all files for a business entity."""
    await verify_entity_access(entity_id, current_user, db)
    
    storage_service = FileStorageService()
    
    file_category = None
    if category:
        try:
            file_category = FileCategory(category)
        except ValueError:
            pass
    
    files = await storage_service.list_files(
        entity_id=entity_id,
        category=file_category,
    )
    
    return [FileInfoResponse(**f) for f in files]


@router.get(
    "/{entity_id}/files/{file_id:path}",
    summary="Download file",
)
async def download_file(
    entity_id: UUID,
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Download a file."""
    await verify_entity_access(entity_id, current_user, db)
    
    # Verify file belongs to entity
    if not file_id.startswith(str(entity_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file",
        )
    
    storage_service = FileStorageService()
    
    try:
        file_content, content_type = await storage_service.download_file(file_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    
    return StreamingResponse(
        BytesIO(file_content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_id.split("/")[-1]}"',
        },
    )


@router.delete(
    "/{entity_id}/files/{file_id:path}",
    response_model=MessageResponse,
    summary="Delete file",
)
async def delete_file(
    entity_id: UUID,
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a file."""
    await verify_entity_access(entity_id, current_user, db)
    
    # Verify file belongs to entity
    if not file_id.startswith(str(entity_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file",
        )
    
    storage_service = FileStorageService()
    deleted = await storage_service.delete_file(file_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    
    return MessageResponse(message="File deleted successfully")


@router.post(
    "/{entity_id}/documents/upload",
    response_model=ReceiptUploadResponse,
    summary="Upload document",
)
async def upload_document(
    entity_id: UUID,
    file: UploadFile = File(...),
    category: str = Query("other", description="Document category"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Upload a general document (invoice, certificate, report, etc.).
    
    No OCR processing - for storing reference documents.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    # Read file content
    file_content = await file.read()
    
    # Check file size (max 25MB for documents)
    max_size = 25 * 1024 * 1024
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 25MB",
        )
    
    # Determine category
    try:
        file_category = FileCategory(category)
    except ValueError:
        file_category = FileCategory.OTHER
    
    storage_service = FileStorageService()
    upload_result = await storage_service.upload_file(
        entity_id=entity_id,
        file_content=file_content,
        filename=file.filename or "document",
        content_type=file.content_type,
        category=file_category,
        metadata={
            "uploaded_by": str(current_user.id),
            "original_filename": file.filename,
        },
    )
    
    return ReceiptUploadResponse(
        file_id=upload_result["file_id"],
        url=upload_result["url"],
        filename=upload_result["filename"],
        content_type=upload_result["content_type"],
        size=upload_result["size"],
        extracted_data=None,
    )
