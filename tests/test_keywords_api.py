from sqlalchemy import select

from app.db import async_session_maker
from app.models import JobKeyword, Keyword, KeywordAlias
from tests.factories import insert_job, insert_job_keyword, insert_keyword


async def test_jobs_for_keyword(client, auth_headers, clean_jobs_table):
    job = await insert_job(company_name="Acme")
    keyword = await insert_keyword(
        canonical_name="KWJobsTest", canonical_key="kwjobstest", category="tool"
    )
    await insert_job_keyword(job.id, keyword.id)

    response = await client.get(f"/keywords/{keyword.id}/jobs", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["company_name"] == "Acme"
    assert response.json()[0]["source_url"] == job.source_url


async def test_delete_keyword_cascades_job_keywords_and_aliases(
    client, auth_headers, clean_jobs_table
):
    job = await insert_job()
    keyword = await insert_keyword(
        canonical_name="DeleteMe", canonical_key="deleteme", category="tool"
    )
    await insert_job_keyword(job.id, keyword.id)

    async with async_session_maker() as session:
        session.add(KeywordAlias(keyword_id=keyword.id, alias_key="deleteme-alias"))
        await session.commit()

    response = await client.delete(f"/keywords/{keyword.id}", headers=auth_headers)
    assert response.status_code == 204

    async with async_session_maker() as session:
        assert await session.get(Keyword, keyword.id) is None
        remaining_jk = (
            await session.execute(select(JobKeyword).where(JobKeyword.keyword_id == keyword.id))
        ).scalars().all()
        assert remaining_jk == []
        remaining_alias = (
            await session.execute(
                select(KeywordAlias).where(KeywordAlias.alias_key == "deleteme-alias")
            )
        ).scalars().all()
        assert remaining_alias == []


async def test_delete_keyword_404_for_unknown_id(client, auth_headers, clean_jobs_table):
    response = await client.delete(
        "/keywords/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


async def test_patch_keyword_rename_and_conflict(client, auth_headers, clean_jobs_table):
    keyword_a = await insert_keyword(
        canonical_name="RenameA", canonical_key="renamea", category="tool"
    )
    keyword_b = await insert_keyword(
        canonical_name="RenameB", canonical_key="renameb", category="tool"
    )

    ok_response = await client.patch(
        f"/keywords/{keyword_a.id}", json={"canonical_name": "Renamed"}, headers=auth_headers
    )
    assert ok_response.status_code == 200
    assert ok_response.json()["canonical_name"] == "Renamed"

    conflict_response = await client.patch(
        f"/keywords/{keyword_b.id}", json={"canonical_name": "Renamed"}, headers=auth_headers
    )
    assert conflict_response.status_code == 409


async def test_merge_keywords_moves_and_dedupes(client, auth_headers, clean_jobs_table):
    job_only_source = await insert_job()
    job_both = await insert_job()

    source = await insert_keyword(
        canonical_name="MergeSource", canonical_key="mergesource", category="tool"
    )
    target = await insert_keyword(
        canonical_name="MergeTarget", canonical_key="mergetarget", category="tool"
    )

    await insert_job_keyword(job_only_source.id, source.id, surface_form="src")
    await insert_job_keyword(job_both.id, source.id, surface_form="src-both")
    await insert_job_keyword(job_both.id, target.id, surface_form="tgt-both")

    response = await client.post(
        "/keywords/merge",
        json={"source_keyword_id": str(source.id), "target_keyword_id": str(target.id)},
        headers=auth_headers,
    )
    assert response.status_code == 200

    async with async_session_maker() as session:
        assert await session.get(Keyword, source.id) is None

        remaining = (
            await session.execute(
                select(JobKeyword).where(JobKeyword.keyword_id == target.id)
            )
        ).scalars().all()
        job_ids = {jk.job_id for jk in remaining}
        assert job_ids == {job_only_source.id, job_both.id}

        alias = (
            await session.execute(
                select(KeywordAlias).where(KeywordAlias.alias_key == "mergesource")
            )
        ).scalar_one()
        assert alias.keyword_id == target.id
