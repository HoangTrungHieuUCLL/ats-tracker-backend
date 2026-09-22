import uuid

from tests.factories import insert_job


async def _register_other_user(client) -> dict:
    username = f"otheruser-{uuid.uuid4().hex[:12]}"
    response = await client.post(
        "/auth/register", json={"username": username, "password": "other-password-123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_cannot_see_another_users_job(client, auth_headers, clean_jobs_table):
    job = await insert_job(company_name="Mine")
    other_headers = await _register_other_user(client)

    response = await client.get(f"/jobs/{job.id}", headers=other_headers)
    assert response.status_code == 404


async def test_job_list_only_shows_own_jobs(client, auth_headers, clean_jobs_table):
    await insert_job(company_name="Mine")
    other_headers = await _register_other_user(client)

    response = await client.get("/jobs", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_cannot_patch_another_users_job(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    other_headers = await _register_other_user(client)

    response = await client.patch(
        f"/jobs/{job.id}", json={"application_status": "applied"}, headers=other_headers
    )
    assert response.status_code == 404


async def test_cannot_delete_another_users_job(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    other_headers = await _register_other_user(client)

    response = await client.delete(f"/jobs/{job.id}", headers=other_headers)
    assert response.status_code == 404


async def test_batch_intake_dedupes_per_user_not_globally(client, auth_headers, clean_jobs_table):
    url = "https://example.com/jobs/shared-url"
    first = await client.post("/jobs/batch", json={"urls": [url]}, headers=auth_headers)
    assert first.json()[0]["result"] == "accepted"

    other_headers = await _register_other_user(client)
    second = await client.post("/jobs/batch", json={"urls": [url]}, headers=other_headers)
    assert second.json()[0]["result"] == "accepted"  # different user, not a duplicate


async def test_cannot_edit_another_users_note(client, auth_headers, clean_jobs_table):
    job = await insert_job()
    create_response = await client.post(
        f"/jobs/{job.id}/notes", json={"body": "private note"}, headers=auth_headers
    )
    note_id = create_response.json()["id"]

    other_headers = await _register_other_user(client)
    response = await client.patch(
        f"/notes/{note_id}", json={"body": "hijacked"}, headers=other_headers
    )
    assert response.status_code == 404
