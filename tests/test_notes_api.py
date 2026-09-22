from tests.factories import insert_job


async def test_add_update_delete_note(client, auth_headers, clean_jobs_table):
    job = await insert_job()

    create_response = await client.post(
        f"/jobs/{job.id}/notes", json={"body": "First note"}, headers=auth_headers
    )
    assert create_response.status_code == 201
    note_id = create_response.json()["id"]
    assert create_response.json()["body"] == "First note"

    update_response = await client.patch(
        f"/notes/{note_id}", json={"body": "Updated note"}, headers=auth_headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["body"] == "Updated note"

    delete_response = await client.delete(f"/notes/{note_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    detail_response = await client.get(f"/jobs/{job.id}", headers=auth_headers)
    assert detail_response.json()["notes"] == []


async def test_add_note_requires_existing_job(client, auth_headers, clean_jobs_table):
    response = await client.post(
        "/jobs/00000000-0000-0000-0000-000000000000/notes",
        json={"body": "x"},
        headers=auth_headers,
    )
    assert response.status_code == 404
