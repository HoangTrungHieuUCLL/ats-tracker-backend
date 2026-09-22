import csv
import io

from tests.factories import insert_job


async def test_export_jobs_csv(client, auth_headers, clean_jobs_table):
    await insert_job(company_name="Acme", job_title="Data Analyst")

    response = await client.get("/export/jobs.csv", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0][:3] == ["id", "company_name", "job_title"]
    assert any(row[1] == "Acme" and row[2] == "Data Analyst" for row in rows[1:])
