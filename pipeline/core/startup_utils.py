"""Startup profile builder — shared between startup_scout script and pipeline server."""


def _build_startup_profile(startup: dict, llm_profile: dict, job_id: int) -> dict:
    """Merge scraper structured data + LLM extraction into a startup profile payload."""
    source = startup.get("source", "")

    # Start with LLM-extracted data
    profile = {
        "job_id": job_id,
        "source": source,
        "startup_name": llm_profile.get("startup_name") or startup.get("company"),
        "website_url": startup.get("job_url") or startup.get("website", ""),
        "one_liner": llm_profile.get("one_liner", ""),
        "product_description": llm_profile.get("product_description", ""),
        "tech_stack": llm_profile.get("tech_stack", []),
        "topics": llm_profile.get("topics", []) or startup.get("topics", []),
        "has_customers": llm_profile.get("has_customers"),
        "has_customers_evidence": llm_profile.get("has_customers_evidence", ""),
        "funding_amount": llm_profile.get("funding_amount", "") or None,
        "funding_round": llm_profile.get("funding_round", "") or None,
        "funding_date": llm_profile.get("funding_date") or None,
        "funding_source": "llm_inferred" if llm_profile.get("funding_round") else None,
        "founder_names": llm_profile.get("founder_names", []),
        "founder_roles": llm_profile.get("founder_roles", []),
        "employee_count": llm_profile.get("employee_count"),
        "employee_count_source": "llm_inferred" if llm_profile.get("employee_count") else None,
        "founding_date": llm_profile.get("founding_date") or None,
        "founding_date_source": "llm_inferred" if llm_profile.get("founding_date") else None,
        "llm_extracted": True,
        "llm_extraction_raw": llm_profile,
    }

    # Source-specific overrides (structured data takes precedence)
    if source == "yc_directory":
        profile["yc_batch"] = startup.get("yc_batch", "")
        profile["yc_url"] = startup.get("yc_url", "")
        if startup.get("founding_date"):
            profile["founding_date"] = str(startup["founding_date"])
            profile["founding_date_source"] = "yc_batch"
        if startup.get("team_size") and startup["team_size"] != 5:  # 5 is the default fallback
            profile["employee_count"] = startup["team_size"]
            profile["employee_count_source"] = "yc_directory"
        # YC companies are at minimum pre-seed funded
        if not profile["funding_round"] or profile["funding_round"] == "unknown":
            profile["funding_round"] = "pre_seed"
            profile["funding_source"] = "yc_batch"

    elif source == "producthunt":
        profile["ph_url"] = startup.get("ph_url", "")
        profile["ph_launch_date"] = str(startup.get("ph_launch_date", "")) or None
        profile["ph_votes_count"] = startup.get("ph_votes_count")
        ph_maker_data = startup.get("ph_maker_data", [])
        if ph_maker_data:
            profile["ph_maker_info"] = str(ph_maker_data)
            if not profile["founder_names"]:
                profile["founder_names"] = [m["name"] for m in ph_maker_data if isinstance(m, dict) and m.get("name")]
        if not profile.get("founding_date") and startup.get("ph_launch_date"):
            profile["founding_date"] = str(startup["ph_launch_date"])
            profile["founding_date_source"] = "ph_launch"

    elif source == "hn_hiring":
        profile["hn_thread_date"] = str(startup.get("date_posted", "")) or None

    # Compute age_months
    if profile.get("founding_date"):
        from datetime import date as date_type
        try:
            fd = date_type.fromisoformat(str(profile["founding_date"]))
            today = date_type.today()
            profile["age_months"] = (today.year - fd.year) * 12 + (today.month - fd.month)
        except (ValueError, TypeError):
            profile["age_months"] = None

    # Compute data_completeness
    profile["data_completeness"] = _compute_completeness(profile)

    return profile


def _compute_completeness(profile: dict) -> int:
    """Score 0-100 based on which key fields are populated."""
    checks = [
        bool(profile.get("startup_name")),
        bool(profile.get("founding_date")),
        bool(profile.get("founder_names")),
        bool(profile.get("product_description") or profile.get("one_liner")),
        bool(profile.get("funding_amount") or profile.get("funding_round")),
        bool(profile.get("funding_round") and profile["funding_round"] != "unknown"),
        profile.get("has_customers") is not None,
        bool(profile.get("employee_count")),
        bool(profile.get("tech_stack")),
        bool(profile.get("topics")),
    ]
    return int(sum(checks) / len(checks) * 100)
