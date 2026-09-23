from app.db import async_session_maker
from app.models import ApplicationStatus, ExtractionMethod, Job, JobStatusHistory, ProcessingStatus
from tests.factories import insert_job


async def test_list_jobs_filters_and_sorts(client, auth_headers, clean_jobs_table):
    await insert_job(company_name="Acme", role_family="data_analyst")
    await insert_job(company_name="Beta", role_family="data_engineer")

    response = await client.get(
        "/jobs", params={"role_family": "data_analyst"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["company_name"] == "Acme"


async def test_list_jobs_search_by_company_or_title(client, auth_headers, clean_jobs_table):
    await insert_job(company_name="Acme Analytics")
    await insert_job(company_name="Other Co", job_title="Acme Integration Engineer")
    await insert_job(company_name="Unrelated")

    response = await client.get("/jobs", params={"q": "acme"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_get_job_detail_includes_keywords_notes_history(
    client, auth_headers, clean_jobs_table
):
    from tests.factories import insert_job_keyword, insert_keyword

    job = await insert_job(raw_text="some text")
    keyword = await insert_keyword(canonical_name="SQL", canonical_key="sql", category="tool")
    await insert_job_keyword(job.id, keyword.id, surface_form="SQL")

    response = await client.get(f"/jobs/{job.id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["raw_text"] == "some text"
    assert len(body["keywords"]) == 1
    assert body["keywords"][0]["canonical_name"] == "SQL"
    assert body["notes"] == []
    assert body["status_history"] == []


async def test_get_job_404(client, auth_headers, clean_jobs_table):
    response = await client.get(
        "/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


async def test_patch_job_writes_status_history_and_tracks_manual_edits(
    client, auth_headers, clean_jobs_table
):
    job = await insert_job(application_status=ApplicationStatus.saved, company_name="Old Name")

    response = await client.patch(
        f"/jobs/{job.id}",
        json={"application_status": "applied", "company_name": "New Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["application_status"] == "applied"
    assert body["company_name"] == "New Name"
    assert "company_name" in body["manually_edited_fields"]

    async with async_session_maker() as session:
        history = (
            await session.execute(
                JobStatusHistory.__table__.select().where(JobStatusHistory.job_id == job.id)
            )
        ).all()
    assert len(history) == 1


async def test_patch_job_does_not_write_history_when_status_unchanged(
    client, auth_headers, clean_jobs_table
):
    job = await insert_job(application_status=ApplicationStatus.saved)

    response = await client.patch(
        f"/jobs/{job.id}", json={"application_status": "saved"}, headers=auth_headers
    )
    assert response.status_code == 200

    async with async_session_maker() as session:
        history = (
            await session.execute(
                JobStatusHistory.__table__.select().where(JobStatusHistory.job_id == job.id)
            )
        ).all()
    assert len(history) == 0


async def test_delete_job(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    response = await client.delete(f"/jobs/{job.id}", headers=auth_headers)
    assert response.status_code == 204

    async with async_session_maker() as session:
        assert await session.get(Job, job.id) is None


async def test_manual_text_rejects_short_text(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    response = await client.put(
        f"/jobs/{job.id}/manual-text", json={"text": "too short"}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_manual_text_accepts_and_requeues(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    long_text = " ".join(["word"] * 200)

    response = await client.put(
        f"/jobs/{job.id}/manual-text", json={"text": long_text}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "needs_review"
    assert body["extraction_method"] == "manual"


async def test_retry_requires_failed_or_needs_manual_text(client, auth_headers, clean_jobs_table):
    job = await insert_job(processing_status=ProcessingStatus.done)
    response = await client.post(f"/jobs/{job.id}/retry", headers=auth_headers)
    assert response.status_code == 409


async def test_retry_resets_job_for_refetch(client, auth_headers, clean_jobs_table):
    job = await insert_job(
        processing_status=ProcessingStatus.failed,
        extraction_method=ExtractionMethod.readability,
        raw_text="stale text",
        attempts=3,
    )
    response = await client.post(f"/jobs/{job.id}/retry", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "queued"
    assert body["extraction_method"] is None
    assert body["raw_text"] is None
    assert body["attempts"] == 0


async def test_reanalyze_requires_raw_text(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    response = await client.post(f"/jobs/{job.id}/reanalyze", headers=auth_headers)
    assert response.status_code == 409


async def test_reanalyze_requeues_without_touching_raw_text(client, auth_headers, clean_jobs_table):
    job = await insert_job(
        processing_status=ProcessingStatus.done,
        extraction_method=ExtractionMethod.json_ld,
        raw_text="kept text",
    )
    response = await client.post(f"/jobs/{job.id}/reanalyze", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "needs_review"
    assert body["raw_text"] == "kept text"


async def test_analyze_requires_needs_review(client, auth_headers, clean_jobs_table):
    job = await insert_job(processing_status=ProcessingStatus.done)
    response = await client.post(f"/jobs/{job.id}/analyze", headers=auth_headers)
    assert response.status_code == 409


async def test_analyze_requeues_job(client, auth_headers, clean_jobs_table):
    job = await insert_job(
        processing_status=ProcessingStatus.needs_review,
        extraction_method=ExtractionMethod.json_ld,
        raw_text="ready to analyze",
    )
    response = await client.post(f"/jobs/{job.id}/analyze", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "queued"
    assert body["raw_text"] == "ready to analyze"


async def test_analyze_404_for_unknown_job(client, auth_headers, clean_jobs_table):
    import uuid

    response = await client.post(f"/jobs/{uuid.uuid4()}/analyze", headers=auth_headers)
    assert response.status_code == 404


async def test_reanalyze_outdated_only_touches_previously_analyzed_jobs(
    client, auth_headers, clean_jobs_table
):
    outdated = await insert_job(
        processing_status=ProcessingStatus.done, raw_text="t", prompt_version="v0"
    )
    current = await insert_job(
        processing_status=ProcessingStatus.done, raw_text="t", prompt_version="v1"
    )
    never_analyzed = await insert_job(
        processing_status=ProcessingStatus.needs_manual_text, raw_text=None, prompt_version=None
    )

    response = await client.post("/jobs/reanalyze-outdated", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["requeued"] == 1

    async with async_session_maker() as session:
        assert (await session.get(Job, outdated.id)).processing_status == ProcessingStatus.queued
        assert (await session.get(Job, current.id)).processing_status == ProcessingStatus.done
        assert (
            await session.get(Job, never_analyzed.id)
        ).processing_status == ProcessingStatus.needs_manual_text  # untouched: never had raw_text
