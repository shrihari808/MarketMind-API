"""
Deep Institutional Equity Research Endpoints.
Supports automated 7-section equity report generation and direct in-memory PDF export.
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status

from app.api.deps import get_deep_research_service
from app.services.deep_research import DeepResearchService
from app.domain.schemas.rag import DeepResearchResult

router = APIRouter(prefix="/research", tags=["Deep Research"])


class ResearchRequest(BaseModel):
    """Payload for initiating an equity research report."""
    company_name: str = Field(..., min_length=2, description="Target company name or ticker (e.g. 'Tata Motors', 'AAPL')")
    country: str = Field(default="IN", description="Country market context (e.g. 'IN', 'US')")
    section_by_section: Optional[bool] = Field(
        default=None,
        description="Override: True for modular granular generation, False for single-pass"
    )


@router.post(
    "",
    response_model=DeepResearchResult,
    summary="Generate 7-Section Institutional Equity Research Report"
)
async def generate_research_report(
    request: ResearchRequest,
    research_service: DeepResearchService = Depends(get_deep_research_service)
) -> DeepResearchResult:
    """
    Synthesizes a 7-section institutional equity research report:
    1. Executive Summary & Investment Thesis
    2. Company Profile & Core Business Model
    3. Fundamental & Valuation Analysis (Markdown tables)
    4. Industry Dynamics & Competitive Moat
    5. Key Risk Factors
    6. Strategic Catalysts & Outlook
    7. Valuation Scenarios (Bull/Base/Bear) & Recommendation
    """
    return await research_service.generate_research_report(
        company_or_ticker=request.company_name,
        country=request.country,
        section_by_section=request.section_by_section
    )


@router.post(
    "/pdf",
    summary="Generate and Download Publication-Ready Equity Report as PDF"
)
async def download_research_pdf(
    request: ResearchRequest,
    research_service: DeepResearchService = Depends(get_deep_research_service)
) -> Response:
    """
    Generates an institutional equity report and compiles a publication-ready PDF in memory
    using ReportLab. Returns the binary PDF stream directly with download headers.
    """
    result = await research_service.generate_research_report(
        company_or_ticker=request.company_name,
        country=request.country,
        section_by_section=request.section_by_section
    )

    try:
        pdf_bytes = research_service.export_pdf(
            markdown_content=result.markdown_report,
            company_name=result.company_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile PDF report: {str(e)}"
        )

    safe_ticker = result.ticker.replace(".", "_")
    filename = f"{safe_ticker}_Equity_Research.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-cache"
        }
    )
