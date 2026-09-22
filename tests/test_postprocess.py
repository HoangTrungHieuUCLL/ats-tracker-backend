from sqlalchemy import select

from app.db import async_session_maker
from app.models import Job, JobKeyword, Keyword, KeywordCategory, ProcessingStatus
from app.services.llm.schema import ExtractedKeyword, JobAnalysis
from app.services.postprocess import apply_analysis
from tests.factories import TEST_USER_ID


async def _insert_job(**overrides) -> Job:
    defaults = dict(
        user_id=TEST_USER_ID,
        source_url="https://example.com/jobs/1",
        normalized_url="https://example.com/jobs/1",
        domain="example.com",
        processing_status=ProcessingStatus.analyzing,
        raw_text="We use PowerBI and SQL daily. Sql is required.",
        manually_edited_fields=[],
    )
    defaults.update(overrides)
    async with async_session_maker() as session:
        job = Job(**defaults)
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def _job_keywords(job_id):
    async with async_session_maker() as session:
        rows = (
            await session.execute(select(JobKeyword).where(JobKeyword.job_id == job_id))
        ).scalars().all()
        return rows


async def test_resolves_existing_alias_and_creates_new_keyword_and_dedupes(clean_jobs_table):
    job = await _insert_job()
    analysis = JobAnalysis(
        job_title="Data Analyst",
        summary="Great role.",
        keywords=[
            ExtractedKeyword(
                canonical_name="PowerBI",
                surface_form="PowerBI",
                category=KeywordCategory.tool,
                importance="must_have",
            ),
            ExtractedKeyword(
                canonical_name="Snowflake",
                surface_form="Snowflake",
                category=KeywordCategory.tool,
                importance="nice_to_have",
            ),
            ExtractedKeyword(
                canonical_name="SQL",
                surface_form="SQL",
                category=KeywordCategory.hard_skill,
                importance="must_have",
            ),
            ExtractedKeyword(
                canonical_name="Sql",
                surface_form="Sql",
                category=KeywordCategory.hard_skill,
                importance="must_have",
            ),
        ],
    )

    async with async_session_maker() as session:
        db_job = await session.get(Job, job.id)
        await apply_analysis(session, db_job, analysis, llm_model="gemini-test")

    job_keywords = await _job_keywords(job.id)
    assert len(job_keywords) == 3  # PowerBI, Snowflake, SQL/Sql collapsed

    async with async_session_maker() as session:
        power_bi = (
            await session.execute(select(Keyword).where(Keyword.canonical_key == "power bi"))
        ).scalar_one()
        snowflake = (
            await session.execute(select(Keyword).where(Keyword.canonical_key == "snowflake"))
        ).scalar_one()
        assert power_bi.canonical_name == "Power BI"  # resolved via seeded alias, not overwritten
        assert snowflake.canonical_name == "Snowflake"

    power_bi_jk = next(jk for jk in job_keywords if jk.surface_form == "PowerBI")
    snowflake_jk = next(jk for jk in job_keywords if jk.surface_form == "Snowflake")
    assert power_bi_jk.evidence_found is True
    assert snowflake_jk.evidence_found is False


async def test_preserves_manually_edited_fields(clean_jobs_table):
    job = await _insert_job(
        job_title="Human Edited Title",
        manually_edited_fields=["job_title"],
    )
    analysis = JobAnalysis(job_title="LLM Suggested Title", location="Munich", keywords=[])

    async with async_session_maker() as session:
        db_job = await session.get(Job, job.id)
        await apply_analysis(session, db_job, analysis, llm_model="gemini-test")

    async with async_session_maker() as session:
        updated = await session.get(Job, job.id)
        assert updated.job_title == "Human Edited Title"
        assert updated.location == "Munich"
        assert updated.processing_status == ProcessingStatus.done
        assert updated.llm_model == "gemini-test"
