from __future__ import annotations

from triallens.models import EvidenceSource, SourceType


def sample_sources(workspace_id: str, condition: str, intervention: str | None) -> list[EvidenceSource]:
    topic = f"{intervention or 'therapy'} and {condition}".strip()
    return [
        EvidenceSource(
            workspace_id=workspace_id,
            source_type=SourceType.pubmed,
            external_id="PMID-DEMO-001",
            title=f"Evidence review for {topic}",
            abstract=(
                f"Recent biomedical literature on {topic} emphasizes clinical outcomes, adverse effects, "
                "patient selection, and the importance of comparing observed benefit against baseline risk. "
                "The available abstracts describe heterogeneous study populations and recommend careful "
                "interpretation when generalizing across age groups and comorbidities."
            ),
            url="https://pubmed.ncbi.nlm.nih.gov/",
            publication_date="2025",
        ),
        EvidenceSource(
            workspace_id=workspace_id,
            source_type=SourceType.clinical_trials,
            external_id="NCT-DEMO-001",
            title=f"Clinical trial landscape for {topic}",
            abstract=(
                f"Registered clinical trials related to {topic} commonly track efficacy endpoints, safety "
                "outcomes, eligibility criteria, trial phase, and recruitment status. Trial records should be "
                "read as protocol and registry evidence, not as completed peer-reviewed results unless posted "
                "outcomes are available."
            ),
            url="https://clinicaltrials.gov/",
            status="Recruiting / Completed mixed",
            phase="Phase 2 / Phase 3 mixed",
        ),
        EvidenceSource(
            workspace_id=workspace_id,
            source_type=SourceType.fda_label,
            external_id="FDA-LABEL-DEMO-001",
            title=f"FDA label sections relevant to {intervention or condition}",
            abstract=(
                "Drug label evidence includes indications, contraindications, warnings, precautions, adverse "
                "reactions, dosage information, and clinically significant interactions. Label sections are "
                "regulatory documents and should be distinguished from comparative effectiveness studies."
            ),
            url="https://open.fda.gov/apis/drug/label/",
        ),
        EvidenceSource(
            workspace_id=workspace_id,
            source_type=SourceType.fda_adverse_event,
            external_id="FDA-AE-DEMO-001",
            title=f"Reported adverse events for {intervention or condition}",
            abstract=(
                "FDA adverse event reports describe suspected events submitted by clinicians, consumers, and "
                "manufacturers. These reports can reveal safety signals and reporting patterns, but they do not "
                "establish incidence rates or prove that a product caused the reported event."
            ),
            url="https://open.fda.gov/apis/drug/event/",
        ),
    ]

