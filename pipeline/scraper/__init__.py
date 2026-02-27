"""Scraper package — import all modules to trigger @scraper decorator registration."""

# Import all scraper modules so their @scraper decorators register with the registry.
# Order doesn't matter — registration happens at import time.
# jobspy_scraper removed — scrapes LinkedIn/Indeed/Glassdoor which prohibit automated access
from scraper import (
    aggregator_scraper,  # noqa: F401 — remoteok, jooble, adzuna, hiringcafe
    api_boards,  # noqa: F401 — jsearch, careerjet, themuse, findwork
    ats_direct,  # noqa: F401 — greenhouse, lever
    remote_boards,  # noqa: F401 — remotive, jobicy, himalayas, arbeitnow
    startup_scouts,  # noqa: F401 — hn_hiring, yc_directory, producthunt
)
