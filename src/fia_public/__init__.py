"""Public, dependency-free Financial Insight Agent prototype."""

from .company_runtime import CompanyRecord, CompanyRegistry
from .evidence_assembly import EvidenceAssembler

__all__ = ["CompanyRecord", "CompanyRegistry", "EvidenceAssembler"]
