from dataclasses import dataclass


PREDEFINED_QUESTIONS = [
    "What is the company’s purpose and main activities?",
    "What is the company’s primary focus?",
    "What is the company’s commitment to risk management?",
    "What is the company’s commitment to energy management?",
    "What is the company’s commitment to data security?",
]

RISK_DIMENSIONS = [
    "Environmental",
    "Social",
    "Governance",
    "Security/Data",
    "Energy",
    "Risk Management",
]


@dataclass(frozen=True)
class ReportDefinition:
    company_id: str
    company_name: str
    file_name: str
    report_year: str
    source_url: str = ""
    source_type: str = "baseline"
    local_path: str | None = None
    document_label: str | None = None


REPORTS = [
    ReportDefinition(
        company_id="tallink-grupp",
        company_name="Tallink Grupp",
        file_name="Tallink-Grupp-Sustainability-Report-2024-ENG-updated.pdf",
        report_year="2024",
        source_url="https://image.tallink.com/image/upload/grupp/documents/sustainability-reports/Tallink-Grupp-Sustainability-Report-2024-ENG-updated.pdf",
    ),
    ReportDefinition(
        company_id="eesti-energia-annual",
        company_name="Eesti Energia",
        file_name="eesti-energia-2025-final-en.pdf",
        report_year="2025",
        source_url="https://public-docs.enefit.com/ettevottest/investorile/eesti-energia-2025-final-en.pdf",
    ),
    ReportDefinition(
        company_id="eesti-energia-spo",
        company_name="Eesti Energia SPO",
        file_name="Eesti-SPO-UoP.pdf",
        report_year="2024",
        source_url="https://public-docs.enefit.ee/ettevottest/investorile/ESG/Eesti-SPO-UoP.pdf",
    ),
]

ALLOWED_REPORT_URLS = {report.source_url for report in REPORTS}
