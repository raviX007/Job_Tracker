# Pydantic Request Models

All request bodies are validated by Pydantic v2 models defined in `api/models.py`.

---

## SaveJobRequest {#savejob}

Used by: `POST /api/jobs`

```python
class SaveJobRequest(BaseModel):
    job_url:          str | None = None
    source:           str | None = None
    discovered_via:   str | None = None
    title:            str | None = None
    company:          str | None = None
    location:         str | None = None
    is_remote:        bool = False
    description:      str | None = None
    salary_min:       int | None = None
    salary_max:       int | None = None
    salary_currency:  str | None = None
    date_posted:      str | None = None     # ISO date string
    dedup_key:        str | None = None
```

---

## SaveAnalysisRequest {#saveanalysis}

Used by: `POST /api/analyses`

```python
class SaveAnalysisRequest(BaseModel):
    job_id:                     int
    profile_id:                 int
    match_score:                int | None = None
    embedding_score:            float | None = None
    skills_required:            list[str] = []
    skills_matched:             list[str] = []
    skills_missing:             list[str] = []
    ats_keywords:               list[str] = []
    experience_required:        str | None = None
    location_compatible:        bool | None = None
    remote_compatible:          bool | None = None
    company_type:               str | None = None
    gap_tolerant:               bool | None = None
    red_flags:                  list[str] = []
    apply_decision:             str | None = None
    cold_email_angle:           str | None = None
    gap_framing_for_this_role:  str | None = None
    route_action:               str | None = None
```

---

## EnqueueEmailRequest {#enqueueemail}

Used by: `POST /api/emails/enqueue`

```python
class EnqueueEmailRequest(BaseModel):
    job_id:                       int
    profile_id:                   int
    recipient_email:              str
    recipient_name:               str = ""
    recipient_role:               str = ""
    recipient_source:             str = ""
    subject:                      str
    body_html:                    str
    body_plain:                   str
    signature:                    str = ""
    email_verified:               bool = False
    email_verification_result:    str = "unverified"
    email_verification_provider:  str = ""
```

---

## UpdateEmailRequest

Used by: `PUT /api/emails/{email_id}/content`

```python
class UpdateEmailRequest(BaseModel):
    subject:    str
    body_plain: str
```

---

## VerifyEmailRequest

Used by: `PUT /api/emails/{email_id}/verify`

```python
class VerifyEmailRequest(BaseModel):
    verification_result:   str
    verification_provider: str
```

---

## EnsureProfileRequest

Used by: `POST /api/profiles/ensure`

```python
class EnsureProfileRequest(BaseModel):
    name:        str
    email:       str
    config_path: str
```

---

## CreateApplicationRequest

Used by: `POST /api/applications`

```python
class CreateApplicationRequest(BaseModel):
    job_id:     int
    profile_id: int
    method:     str
    platform:   str = ""
```

---

## UpsertApplicationRequest

Used by: `POST /api/applications/upsert`

```python
class UpsertApplicationRequest(BaseModel):
    job_id:        int
    profile_id:    int
    method:        str
    platform:      str = ""
    response_type: str | None = None
    notes:         str | None = None
    app_id:        int | None = None
```

---

## UpdateOutcomeRequest

Used by: `PUT /api/applications/{app_id}/outcome`

```python
class UpdateOutcomeRequest(BaseModel):
    response_type: str
    response_date: str | None = None   # ISO date string
    notes:         str = ""
```

---

## UpdateCoverLetterRequest

Used by: `PUT /api/analyses/cover-letter`

```python
class UpdateCoverLetterRequest(BaseModel):
    job_id:       int
    profile_id:   int
    cover_letter: str
```

---

## DedupCheckRequest

Used by: `POST /api/jobs/dedup-check`

```python
class DedupCheckRequest(BaseModel):
    urls:       list[str] = []
    dedup_keys: list[str] = []
```

---

## SaveStartupProfileRequest {#savestartupprofilerequest}

Used by: `POST /api/startup-profiles`

```python
class SaveStartupProfileRequest(BaseModel):
    job_id:                  int
    startup_name:            str | None = None
    website_url:             str | None = None
    yc_url:                  str | None = None
    ph_url:                  str | None = None
    founding_date:           str | None = None
    founding_date_source:    str | None = None
    age_months:              int | None = None
    founder_names:           list[str] = []
    founder_emails:          list[str] = []
    founder_roles:           list[str] = []
    employee_count:          int | None = None
    employee_count_source:   str | None = None
    one_liner:               str | None = None
    product_description:     str | None = None
    tech_stack:              list[str] = []
    topics:                  list[str] = []
    has_customers:           bool | None = None
    has_customers_evidence:  str | None = None
    funding_amount:          str | None = None
    funding_round:           str | None = None
    funding_date:            str | None = None
    funding_source:          str | None = None
    source:                  str | None = None
    yc_batch:                str | None = None
    ph_launch_date:          str | None = None
    ph_votes_count:          int | None = None
    ph_maker_info:           str | None = None
    hn_thread_date:          str | None = None
    llm_extracted:           bool = False
    llm_extraction_raw:      dict | None = None
    data_completeness:       int | None = None
```

---

## RunPipelineRequest

Used by: `POST /api/pipeline/run`

```python
class RunPipelineRequest(BaseModel):
    source: str = "all"
    limit:  int = 10
```
