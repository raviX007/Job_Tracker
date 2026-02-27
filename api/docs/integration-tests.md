# Integration Tests

Multi-endpoint flow tests that verify endpoints work together correctly. Located in `tests/integration/`.

---

## Unit Tests vs Integration Tests

| Aspect | Unit Tests (`tests/test_*.py`) | Integration Tests (`tests/integration/`) |
|--------|-------------------------------|------------------------------------------|
| Scope | Single endpoint | Multiple endpoints in sequence |
| Goal | Verify one route's logic | Verify end-to-end flows |
| DB | Mock (same mock_pool) | Mock (same mock_pool) |
| Example | "POST /api/jobs returns 201" | "Save job → analyze → enqueue email" |

Both use the same `mock_pool` + `authed_client` fixtures — no real PostgreSQL needed.

---

## Running Tests

```bash
cd api

# Run only integration tests
pytest tests/integration/ -v

# Run only unit tests
pytest tests/ --ignore=tests/integration/ -v

# Run all tests (unit + integration)
pytest tests/ -v

# Run by marker
pytest -m integration -v
```

---

## Test Coverage

### Pipeline Lifecycle (`test_pipeline_lifecycle.py`)

| Test | Flow |
|------|------|
| `test_pipeline_run_then_callback_then_poll` | POST run → PATCH callback (running) → PATCH callback (completed) → GET poll |
| `test_concurrent_run_blocked` | Simulate active run → POST second run → 409 |
| `test_callback_unknown_run_id` | PATCH callback with bad ID → 404 |
| `test_callback_noop_empty_body` | PATCH callback with empty body → no-op |
| `test_poll_nonexistent_run` | GET run with bad ID → 404 |
| `test_list_pipeline_runs` | GET /api/pipeline/runs → list |

### Job-to-Email Flow (`test_job_to_email_flow.py`)

| Test | Flow |
|------|------|
| `test_save_job_then_analyze_then_enqueue_email` | POST job → POST analysis → POST email |
| `test_dedup_check_finds_existing_job` | POST dedup-check → verify existing/new detection |
| `test_ensure_profile_then_save_job` | POST profile → POST job |
| `test_save_analysis_then_update_cover_letter` | POST analysis → PUT cover letter |
| `test_enqueue_email_then_verify` | POST email → PUT verify → PUT advance |

---

## Writing New Integration Tests

1. Create a new file in `tests/integration/` with the `test_` prefix
2. Import fixtures from `conftest`:
   ```python
   from conftest import _mock_row
   ```
3. Mark tests with `@pytest.mark.integration`:
   ```python
   @pytest.mark.integration
   def test_my_flow(authed_client):
       client, conn = authed_client
       # ... test multiple endpoints in sequence
   ```
4. Each step should:
   - Set up mock return values on `conn` (fetchval, fetchrow, fetch, execute)
   - Make an HTTP request via `client`
   - Assert the response status and body
5. Pass values between steps (e.g., IDs returned from one endpoint used in the next)
