import asyncio
import json
import logging
from collections.abc import Callable

from backend.models.research import SearchResult
from backend.services.llm import agenerate_response, llm_concurrency_limit
from backend.services.source_context import format_sources


logger = logging.getLogger("agentlab")

REPORT_SECTIONS = (
    ("Executive Summary", 600),
    ("Key Findings", 700),
    ("Analysis", 800),
    ("Verified Findings", 700),
    ("Limitations and Uncertainty", 600),
    ("Conclusion", 400),
)


class ReportAgent:
    def run(
        self,
        topic: str,
        research: str,
        analysis: str,
        verification: str,
        sources: list[SearchResult],
        document_context: str = "",
        on_section: Callable[[int, str, str], None] | None = None,
    ) -> str:
        return asyncio.run(
            self.arun(
                topic,
                research,
                analysis,
                verification,
                sources,
                document_context,
                on_section,
            )
        )

    async def arun(
        self,
        topic: str,
        research: str,
        analysis: str,
        verification: str,
        sources: list[SearchResult],
        document_context: str = "",
        on_section: Callable[[int, str, str], None] | None = None,
    ) -> str:
        source_context = format_sources(sources)
        document_context = document_context[:3000]
        prompts = (
            (
                f"Write a concise executive summary about {topic}. State the most "
                "important conclusions and uncertainty.\n\n"
                f"Research:\n{research[:2500]}\n\nAnalysis:\n{analysis[:2500]}\n\n"
                f"Verification:\n{verification[:2500]}\n\nDocuments:\n{document_context}"
            ),
            (
                f"List the most important evidence-supported findings about {topic}. "
                "Be specific and avoid repetition.\n\n"
                f"Research:\n{research[:3500]}\n\nAnalysis:\n{analysis[:1500]}\n\n"
                f"Sources:\n{source_context[:3000]}\n\nDocuments:\n{document_context}"
            ),
            (
                f"Explain the main implications, patterns, trade-offs, and disagreements "
                f"about {topic}, without introducing unsupported facts.\n\n"
                f"Analysis:\n{analysis[:3500]}\n\nResearch:\n{research[:2000]}\n\n"
                f"Sources:\n{source_context[:2000]}"
            ),
            (
                f"Summarize what is and is not verified about {topic}. Retain verdicts "
                "and source references; do not overstate evidence.\n\n"
                f"Verification:\n{verification[:4000]}\n\n"
                f"Research:\n{research[:1800]}\n\nSources:\n{source_context[:2200]}"
            ),
            (
                f"Describe material limitations, evidence gaps, and uncertainty in the "
                f"research on {topic}. Do not speculate.\n\n"
                f"Verification:\n{verification[:3000]}\n\n"
                f"Analysis:\n{analysis[:2500]}\n\nSources:\n{source_context[:2000]}"
            ),
            (
                f"Write a concise conclusion for the research on {topic}. Distinguish "
                "supported conclusions from open questions.\n\n"
                f"Research:\n{research[:2000]}\n\nAnalysis:\n{analysis[:2000]}\n\n"
                f"Verification:\n{verification[:2200]}"
            ),
        )

        async def generate_section(index: int, section: str, prompt: str, limit: int):
            try:
                content = await agenerate_response(
                    prompt,
                    system_prompt=(
                        "You are the Report Agent in a multi-agent research system. "
                        "Write only the requested report section, grounded in supplied evidence."
                    ),
                    stage="report",
                    max_output_tokens=limit,
                )
            except Exception:
                logger.exception(
                    "report_section_failed index=%d section=%s",
                    index,
                    section,
                )
                return section, None
            if on_section is not None:
                try:
                    on_section(index, section, content)
                except Exception:
                    logger.exception(
                        "report_section_progress_callback_failed section=%s",
                        section,
                    )
            return section, content

        async with llm_concurrency_limit(5):
            generated = await asyncio.gather(
                *(
                    generate_section(index, section, prompt, token_limit)
                    for index, ((section, token_limit), prompt) in enumerate(
                        zip(REPORT_SECTIONS, prompts, strict=True)
                    )
                )
            )

        streamed_sections = {
            section
            for section, content in generated
            if isinstance(content, str) and content.strip()
        }
        contents = {
            section: content
            for section, content in generated
            if isinstance(content, str) and content.strip()
        }
        missing_sections = [
            section for section, _ in REPORT_SECTIONS if section not in contents
        ]
        if missing_sections:
            try:
                fallback_response = await agenerate_response(
                    f"""Fill only these missing report sections: {missing_sections}

Return one JSON object mapping each exact section name to concise Markdown text.
Use only the evidence below and do not invent facts.

Research:
{research[:3500]}

Analysis:
{analysis[:3500]}

Verification:
{verification[:3500]}

Sources:
{source_context[:4500]}

Documents:
{document_context}""",
                    system_prompt=(
                        "You are a report-writing fallback. Return only a JSON object "
                        "with the requested section names as keys."
                    ),
                    stage="report",
                    response_format="json",
                    max_output_tokens=min(
                        2400,
                        sum(
                            token_limit
                            for section, token_limit in REPORT_SECTIONS
                            if section in missing_sections
                        ),
                    ),
                )
                fallback_sections = json.loads(fallback_response)
                if isinstance(fallback_sections, dict):
                    for section in missing_sections:
                        value = fallback_sections.get(section)
                        if isinstance(value, str) and value.strip():
                            contents[section] = value
            except Exception:
                logger.exception("report_missing_sections_fallback_failed")

        evidence_fallbacks = {
            "Executive Summary": research[:800],
            "Key Findings": research[:1200],
            "Analysis": analysis[:1400],
            "Verified Findings": verification[:1200],
            "Limitations and Uncertainty": (
                "The available sources and verification notes define the limits "
                "of what can be concluded.\n\n" + verification[:900]
            ),
            "Conclusion": verification[:900] or research[:900],
        }

        report_parts = [f"# {topic}"]
        for index, (section, _) in enumerate(REPORT_SECTIONS):
            content = contents.get(section, "").strip()
            if not content:
                content = evidence_fallbacks[section].strip()
                if not content:
                    content = "No supported information was available for this section."
                logger.warning("report_section_using_evidence_fallback section=%s", section)
            if on_section is not None and section not in streamed_sections:
                on_section(index, section, content)
            report_parts.append(f"## {section}\n\n{content}")

        sources_section = "\n".join(
            f"- [{source.title}]({source.url})" for source in sources
        )
        report_parts.append(f"## Sources\n\n{sources_section or 'No web sources were found.'}")
        return "\n\n".join(report_parts)
