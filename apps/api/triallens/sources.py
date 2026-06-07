from __future__ import annotations

import html
import xml.etree.ElementTree as ET

import httpx

from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.sample_data import sample_sources
from triallens.text import normalize


class SourceClient:
    async def fetch(self, workspace: Workspace) -> list[EvidenceSource]:
        raise NotImplementedError


class PubMedClient(SourceClient):
    async def fetch(self, workspace: Workspace) -> list[EvidenceSource]:
        query = f"{workspace.condition} {workspace.intervention or ''}".strip()
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                search = await client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                    params={"db": "pubmed", "term": query, "retmode": "json", "retmax": 5},
                )
                search.raise_for_status()
                ids = search.json()["esearchresult"].get("idlist", [])
                if not ids:
                    return []
                fetch = await client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                    params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
                )
                fetch.raise_for_status()
            root = ET.fromstring(fetch.text)
            records: list[EvidenceSource] = []
            for article in root.findall(".//PubmedArticle"):
                pmid = article.findtext(".//PMID") or "unknown"
                title = normalize(" ".join(article.findtext(".//ArticleTitle", default="").split()))
                abstract = normalize(" ".join(node.text or "" for node in article.findall(".//AbstractText")))
                year = article.findtext(".//PubDate/Year")
                if title and abstract:
                    records.append(
                        EvidenceSource(
                            workspace_id=workspace.id,
                            source_type=SourceType.pubmed,
                            external_id=pmid,
                            title=html.unescape(title),
                            abstract=html.unescape(abstract),
                            publication_date=year,
                            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        )
                    )
            return records
        except Exception:
            return []


class ClinicalTrialsClient(SourceClient):
    async def fetch(self, workspace: Workspace) -> list[EvidenceSource]:
        query = f"{workspace.condition} {workspace.intervention or ''}".strip()
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://clinicaltrials.gov/api/v2/studies",
                    params={"query.term": query, "pageSize": 5, "format": "json"},
                )
                response.raise_for_status()
            records = []
            for study in response.json().get("studies", []):
                protocol = study.get("protocolSection", {})
                ident = protocol.get("identificationModule", {})
                status = protocol.get("statusModule", {})
                design = protocol.get("designModule", {})
                description = protocol.get("descriptionModule", {})
                nct_id = ident.get("nctId", "unknown")
                title = ident.get("briefTitle") or ident.get("officialTitle") or nct_id
                abstract = normalize(
                    " ".join(
                        [
                            description.get("briefSummary", ""),
                            description.get("detailedDescription", ""),
                        ]
                    )
                )
                if abstract:
                    records.append(
                        EvidenceSource(
                            workspace_id=workspace.id,
                            source_type=SourceType.clinical_trials,
                            external_id=nct_id,
                            title=title,
                            abstract=abstract,
                            url=f"https://clinicaltrials.gov/study/{nct_id}",
                            status=status.get("overallStatus"),
                            phase=", ".join(design.get("phases", [])) if design.get("phases") else None,
                        )
                    )
            return records
        except Exception:
            return []


class OpenFdaClient(SourceClient):
    async def fetch(self, workspace: Workspace) -> list[EvidenceSource]:
        term = workspace.intervention or workspace.condition
        records: list[EvidenceSource] = []
        records.extend(await self._fetch_label(workspace, term))
        records.extend(await self._fetch_events(workspace, term))
        return records

    async def _fetch_label(self, workspace: Workspace, term: str) -> list[EvidenceSource]:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://api.fda.gov/drug/label.json",
                    params={"search": f'openfda.generic_name:"{term}"', "limit": 3},
                )
                response.raise_for_status()
            records = []
            for idx, item in enumerate(response.json().get("results", []), start=1):
                openfda = item.get("openfda", {})
                title = ", ".join(openfda.get("brand_name") or openfda.get("generic_name") or [term])
                sections = []
                for key in ["indications_and_usage", "warnings", "adverse_reactions", "drug_interactions"]:
                    sections.extend(item.get(key, [])[:1])
                abstract = normalize(" ".join(sections))
                if abstract:
                    records.append(
                        EvidenceSource(
                            workspace_id=workspace.id,
                            source_type=SourceType.fda_label,
                            external_id=f"FDA-LABEL-{term}-{idx}",
                            title=f"FDA label: {title}",
                            abstract=abstract,
                            url="https://open.fda.gov/apis/drug/label/",
                        )
                    )
            return records
        except Exception:
            return []

    async def _fetch_events(self, workspace: Workspace, term: str) -> list[EvidenceSource]:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://api.fda.gov/drug/event.json",
                    params={
                        "search": f'patient.drug.openfda.generic_name:"{term}"',
                        "count": "patient.reaction.reactionmeddrapt.exact",
                        "limit": 5,
                    },
                )
                response.raise_for_status()
            top = response.json().get("results", [])
            if not top:
                return []
            summary = "; ".join(f"{item['term']} ({item['count']} reports)" for item in top[:5])
            return [
                EvidenceSource(
                    workspace_id=workspace.id,
                    source_type=SourceType.fda_adverse_event,
                    external_id=f"FDA-AE-{term}",
                    title=f"openFDA adverse event report counts for {term}",
                    abstract=(
                        f"Top reported reactions in openFDA for {term}: {summary}. "
                        "These are spontaneous reports and cannot establish causality or incidence."
                    ),
                    url="https://open.fda.gov/apis/drug/event/",
                )
            ]
        except Exception:
            return []


async def fetch_sources(workspace: Workspace) -> list[EvidenceSource]:
    sources: list[EvidenceSource] = []
    if SourceType.pubmed in workspace.source_types:
        sources.extend(await PubMedClient().fetch(workspace))
    if SourceType.clinical_trials in workspace.source_types:
        sources.extend(await ClinicalTrialsClient().fetch(workspace))
    if SourceType.fda_label in workspace.source_types or SourceType.fda_adverse_event in workspace.source_types:
        sources.extend(await OpenFdaClient().fetch(workspace))

    selected = [source for source in sources if source.source_type in workspace.source_types]
    if selected:
        return selected
    return [source for source in sample_sources(workspace.id, workspace.condition, workspace.intervention) if source.source_type in workspace.source_types]

