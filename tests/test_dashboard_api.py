from app.models import ProcessingStatus
from tests.factories import insert_job, insert_job_keyword, insert_keyword


async def test_dashboard_keywords_share_and_evidence_filter(client, auth_headers, clean_jobs_table):
    job1 = await insert_job(processing_status=ProcessingStatus.done, role_family="data_analyst")
    job2 = await insert_job(processing_status=ProcessingStatus.done, role_family="data_analyst")
    await insert_job(processing_status=ProcessingStatus.queued, role_family="data_analyst")

    sql = await insert_keyword(
        canonical_name="DashboardSQL", canonical_key="dashboardsql", category="hard_skill"
    )
    python = await insert_keyword(
        canonical_name="DashboardPython", canonical_key="dashboardpython", category="hard_skill"
    )

    await insert_job_keyword(
        job1.id, sql.id, surface_form="SQL", importance="must_have", evidence_found=True
    )
    await insert_job_keyword(
        job2.id, sql.id, surface_form="SQL", importance="nice_to_have", evidence_found=True
    )
    await insert_job_keyword(
        job2.id, python.id, surface_form="Python", importance="must_have", evidence_found=False
    )

    response = await client.get(
        "/dashboard/keywords",
        params={"role_family": "data_analyst"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["n_jobs"] == 2  # only the two 'done' jobs count

    by_name = {item["canonical_name"]: item for item in body["items"]}
    assert by_name["DashboardSQL"]["job_count"] == 2
    assert by_name["DashboardSQL"]["share"] == 1.0
    assert by_name["DashboardSQL"]["must_have_count"] == 1
    assert by_name["DashboardSQL"]["nice_to_have_count"] == 1
    assert "DashboardPython" not in by_name  # unverified, excluded by default

    response = await client.get(
        "/dashboard/keywords",
        params={"role_family": "data_analyst", "include_unverified": True},
        headers=auth_headers,
    )
    by_name = {item["canonical_name"]: item for item in response.json()["items"]}
    assert by_name["DashboardPython"]["job_count"] == 1
    assert by_name["DashboardPython"]["share"] == 0.5


async def test_dashboard_summary_counts(client, auth_headers, clean_jobs_table):
    await insert_job(
        processing_status=ProcessingStatus.done,
        application_status="applied",
        role_family="data_engineer",
    )
    await insert_job(
        processing_status=ProcessingStatus.done,
        application_status="applied",
        role_family="data_engineer",
    )
    await insert_job(application_status="saved")

    response = await client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["by_application_status"]["applied"] == 2
    assert body["by_application_status"]["saved"] == 1
    assert body["by_role_family"]["data_engineer"] == 2
