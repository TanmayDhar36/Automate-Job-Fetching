"""
Daily job opportunity automation script.

What it does:
1) Collects live job listings by scraping Naukri, LinkedIn, and Indeed search pages.
2) Filters for selected roles such as Data Analyst, Data Scientist, ML Engineer, Business Analyst, and Management Trainee MBA in India (Remote, Bangalore, Kolkata).
3) Generates a professional PDF report with clickable apply links.

Output:
- jobs.pdf in the script directory.

Dependencies for live scraping:
- reportlab
- beautifulsoup4
- selenium
- webdriver-manager
"""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List
from urllib.parse import quote_plus, urljoin

import requests

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class JobListing:
    """Represents a single job listing."""

    title: str
    company: str
    location: str
    experience: str
    apply_link: str
    source: str


ROLE_QUERIES = [
    "Data Analyst",
    "Data Scientist",
    "ML Engineer",
    "Business Analyst",
    "Management Trainee MBA",
]
LOCATION_QUERIES = ["India", "Bangalore, India", "Kolkata, India", "Remote India"]
EXPERIENCE_LEVELS = ["Fresher", "0 to 2 years", "More experience"]
ALL_ROLES_OPTION = "All roles"


def collect_mock_job_listings() -> List[JobListing]:
    """
    Return mock job listings.

    Useful as an offline fallback if live RSS requests fail.
    """
    return [
        JobListing(
            title="Data Analyst",
            company="Insight Metrics",
            location="Bangalore, India",
            experience="Fresher",
            apply_link="https://example.com/jobs/insight-metrics-data-analyst",
            source="Mock",
        ),
        JobListing(
            title="Business Analyst",
            company="FinEdge Solutions",
            location="Remote - India",
            experience="0-2 years",
            apply_link="https://example.com/jobs/finedge-business-analyst",
            source="Mock",
        ),
        JobListing(
            title="Senior Data Analyst",
            company="RetailPulse",
            location="Kolkata, India",
            experience="4+ years",
            apply_link="https://example.com/jobs/retailpulse-senior-data-analyst",
            source="Mock",
        ),
        JobListing(
            title="Data Engineer",
            company="DataForge",
            location="Pune, India",
            experience="2-4 years",
            apply_link="https://example.com/jobs/dataforge-data-engineer",
            source="Mock",
        ),
        JobListing(
            title="Business Analyst - Growth",
            company="CloudVista",
            location="Mumbai, India",
            experience="3+ years",
            apply_link="https://example.com/jobs/cloudvista-growth-analyst",
            source="Mock",
        ),
        JobListing(
            title="Junior Analyst",
            company="Northwind Analytics",
            location="Bangalore, India",
            experience="0-1 years",
            apply_link="https://example.com/jobs/northwind-junior-analyst",
            source="Mock",
        ),
    ]


def _slugify(value: str) -> str:
    """Convert text to a Naukri-style URL slug."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return re.sub(r"-+", "-", cleaned).strip("-")


def _build_naukri_url(role_query: str, location_query: str) -> str:
    """Build a Naukri URL from role and location queries."""
    role_slug = _slugify(role_query)
    location_slug = _slugify(location_query.replace(",", ""))
    return f"https://www.naukri.com/{role_slug}-jobs-in-{location_slug}"


def _build_linkedin_url(role_query: str, location_query: str) -> str:
    """Build a LinkedIn jobs search URL from role and location queries."""
    return (
        "https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(role_query)}&location={quote_plus(location_query)}"
    )


def _build_indeed_url(role_query: str, location_query: str) -> str:
    """Build an Indeed India jobs search URL from role and location queries."""
    return (
        "https://in.indeed.com/jobs"
        f"?q={quote_plus(role_query)}&l={quote_plus(location_query)}"
    )


def _extract_jobs_from_naukri_page(html: str) -> List[JobListing]:
    """Parse rendered Naukri HTML to extract title/company/location/link."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    jobs: List[JobListing] = []

    # Naukri markup can vary; keep multiple selectors for resilience.
    cards = soup.select("article.jobTuple")
    if not cards:
        cards = soup.select("div.srp-jobtuple-wrapper")
    if not cards:
        cards = soup.select("div.cust-job-tuple")

    for card in cards:
        title_node = card.select_one("a.title") or card.select_one("a[title]")
        company_node = card.select_one("a.comp-name") or card.select_one("span.comp-name")
        location_node = (
            card.select_one("span.locWdth")
            or card.select_one("span.loc-wrap")
            or card.select_one("li.location span")
        )

        title = title_node.get_text(strip=True) if title_node else ""
        company = company_node.get_text(strip=True) if company_node else "Unknown Company"
        location = location_node.get_text(" ", strip=True) if location_node else "India"
        experience_node = card.select_one("span.expwdth") or card.select_one("li.experience span")
        experience = experience_node.get_text(" ", strip=True) if experience_node else "Not specified"
        apply_link = title_node.get("href", "").strip() if title_node else ""

        if title and apply_link:
            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    experience=experience,
                    apply_link=apply_link,
                    source="Naukri",
                )
            )

    return jobs


def _extract_jobs_from_linkedin_page(html: str) -> List[JobListing]:
    """Parse rendered LinkedIn jobs HTML to extract title/company/location/link."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    jobs: List[JobListing] = []

    cards = soup.select("li div.base-card")
    if not cards:
        cards = soup.select("li")

    for card in cards:
        title_node = card.select_one("h3.base-search-card__title") or card.select_one("h3")
        company_node = card.select_one("h4.base-search-card__subtitle") or card.select_one("h4")
        location_node = card.select_one("span.job-search-card__location") or card.select_one("span")
        link_node = card.select_one("a.base-card__full-link") or card.select_one("a[href]")

        title = title_node.get_text(" ", strip=True) if title_node else ""
        company = company_node.get_text(" ", strip=True) if company_node else "Unknown Company"
        location = location_node.get_text(" ", strip=True) if location_node else "India"
        experience = "Not specified"
        apply_link = link_node.get("href", "").strip() if link_node else ""

        if title and apply_link:
            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    experience=experience,
                    apply_link=apply_link,
                    source="LinkedIn",
                )
            )

    return jobs


def _extract_jobs_from_indeed_page(html: str) -> List[JobListing]:
    """Parse rendered Indeed HTML to extract title/company/location/link."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    jobs: List[JobListing] = []

    cards = soup.select("div.job_seen_beacon")
    if not cards:
        cards = soup.select("a.tapItem")

    for card in cards:
        title_node = (
            card.select_one("h2.jobTitle span")
            or card.select_one("a.jcs-JobTitle span")
            or card.select_one("h2")
        )
        company_node = card.select_one("span.companyName") or card.select_one("span[data-testid='company-name']")
        location_node = card.select_one("div.companyLocation") or card.select_one("div[data-testid='text-location']")
        link_node = card.select_one("a.jcs-JobTitle") or card.select_one("a[href]")

        title = title_node.get_text(" ", strip=True) if title_node else ""
        company = company_node.get_text(" ", strip=True) if company_node else "Unknown Company"
        location = location_node.get_text(" ", strip=True) if location_node else "India"
        experience_node = card.select_one("div.metadata.salary-snippet-container + div")
        experience = experience_node.get_text(" ", strip=True) if experience_node else "Not specified"
        apply_link_raw = link_node.get("href", "").strip() if link_node else ""
        apply_link = urljoin("https://in.indeed.com", apply_link_raw)

        if title and apply_link:
            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    experience=experience,
                    apply_link=apply_link,
                    source="Indeed",
                )
            )

    return jobs


def fetch_remotive_jobs(role_query: str, timeout_seconds: int = 20) -> List[JobListing]:
    """Fetch jobs from the public Remotive API."""
    jobs: List[JobListing] = []
    url = f"https://remotive.com/api/remote-jobs?search={quote_plus(role_query)}"

    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()

    for item in payload.get("jobs", []):
        title = (item.get("title") or "").strip()
        company = (item.get("company_name") or "Unknown Company").strip()
        location = (item.get("candidate_required_location") or "Remote").strip()
        apply_link = (item.get("url") or "").strip()

        if title and apply_link:
            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    experience="Not specified",
                    apply_link=apply_link,
                    source="Remotive",
                )
            )

    return jobs


def fetch_arbeitnow_jobs(role_query: str, timeout_seconds: int = 20) -> List[JobListing]:
    """Fetch jobs from the public Arbeitnow API."""
    jobs: List[JobListing] = []
    url = "https://www.arbeitnow.com/api/job-board-api"

    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()

    query_lower = role_query.lower()

    for item in payload.get("data", []):
        title = (item.get("title") or "").strip()
        if query_lower not in title.lower():
            continue

        company = (item.get("company_name") or "Unknown Company").strip()
        location = (item.get("location") or "Remote").strip()
        apply_link = (item.get("url") or "").strip()

        if title and apply_link:
            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    location=location,
                    experience="Not specified",
                    apply_link=apply_link,
                    source="Arbeitnow",
                )
            )

    return jobs


def _create_webdriver():
    """Create a headless Chrome WebDriver for scraping."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )

    # Streamlit Cloud/GitHub deployments usually provide Chromium at these paths.
    chromium_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ]
    for path in chromium_paths:
        if shutil.which(path) or Path(path).exists():
            chrome_options.binary_location = path
            break

    # Prefer Selenium Manager first (works well on managed Linux hosts).
    try:
        return webdriver.Chrome(options=chrome_options)
    except Exception:
        # Fallback for local machines that rely on webdriver-manager.
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)


def fetch_naukri_jobs(role_query: str, location_query: str, timeout_seconds: int = 20) -> List[JobListing]:
    """Fetch and parse live jobs from a Naukri search URL."""
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    url = _build_naukri_url(role_query, location_query)
    driver = _create_webdriver()
    try:
        driver.get(url)

        # Wait until common listing wrappers appear.
        wait = WebDriverWait(driver, timeout_seconds)
        try:
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.jobTuple")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.srp-jobtuple-wrapper")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.cust-job-tuple")),
                )
            )
        except TimeoutException:
            return []

        return _extract_jobs_from_naukri_page(driver.page_source)
    finally:
        driver.quit()


def fetch_linkedin_jobs(role_query: str, location_query: str, timeout_seconds: int = 20) -> List[JobListing]:
    """Fetch and parse live jobs from a LinkedIn search URL."""
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    url = _build_linkedin_url(role_query, location_query)
    driver = _create_webdriver()
    try:
        driver.get(url)

        wait = WebDriverWait(driver, timeout_seconds)
        try:
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-card")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h3.base-search-card__title")),
                )
            )
        except TimeoutException:
            return []

        return _extract_jobs_from_linkedin_page(driver.page_source)
    finally:
        driver.quit()


def fetch_indeed_jobs(role_query: str, location_query: str, timeout_seconds: int = 20) -> List[JobListing]:
    """Fetch and parse live jobs from an Indeed search URL."""
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    url = _build_indeed_url(role_query, location_query)
    driver = _create_webdriver()
    try:
        driver.get(url)

        wait = WebDriverWait(driver, timeout_seconds)
        try:
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.job_seen_beacon")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.tapItem")),
                )
            )
        except TimeoutException:
            return []

        return _extract_jobs_from_indeed_page(driver.page_source)
    finally:
        driver.quit()


def _deduplicate_jobs(listings: Iterable[JobListing]) -> List[JobListing]:
    """Deduplicate jobs by title, company, location, and link."""
    deduped: List[JobListing] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for job in listings:
        key = (
            job.title.lower().strip(),
            job.company.lower().strip(),
            job.location.lower().strip(),
            job.experience.lower().strip(),
            job.apply_link.strip(),
            job.source.lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(job)
    return deduped


def collect_live_job_listings(
    role_queries: List[str] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> List[JobListing]:
    """Collect live jobs from Naukri, LinkedIn, and Indeed across role/location combinations."""
    all_jobs: List[JobListing] = []
    active_role_queries = role_queries or ROLE_QUERIES

    fetchers = [
        ("Naukri", fetch_naukri_jobs),
        ("LinkedIn", fetch_linkedin_jobs),
        ("Indeed", fetch_indeed_jobs),
    ]
    api_fetchers = [
        ("Remotive", fetch_remotive_jobs),
        ("Arbeitnow", fetch_arbeitnow_jobs),
    ]
    total_steps = (len(active_role_queries) * len(LOCATION_QUERIES) * len(fetchers)) + (
        len(active_role_queries) * len(api_fetchers)
    )
    completed_steps = 0

    for role in active_role_queries:
        for source_name, fetcher in api_fetchers:
            status_message = f"Fetching {source_name}: {role}"
            try:
                all_jobs.extend(fetcher(role))
            except Exception as exc:
                print(f"Warning: failed to fetch from {source_name} for '{role}': {exc}")
            finally:
                completed_steps += 1
                if progress_callback:
                    progress_callback(completed_steps, total_steps, status_message)

    for role in active_role_queries:
        for location in LOCATION_QUERIES:
            for source_name, fetcher in fetchers:
                status_message = f"Fetching {source_name}: {role} in {location}"
                try:
                    all_jobs.extend(fetcher(role, location))
                except Exception as exc:
                    # Continue on source/query errors so one failure doesn't break the full report.
                    print(
                        f"Warning: failed to fetch from {source_name} for '{role}' in '{location}': {exc}"
                    )
                finally:
                    completed_steps += 1
                    if progress_callback:
                        progress_callback(completed_steps, total_steps, status_message)

    return _deduplicate_jobs(all_jobs)


def _get_role_keywords(role_name: str) -> list[str]:
    """Return searchable keywords for a selected role option."""
    key = role_name.lower().strip()
    role_keyword_map = {
        "data analyst": ["data analyst"],
        "data scientist": ["data scientist"],
        "ml engineer": ["ml engineer", "machine learning engineer", "machine-learning engineer"],
        "business analyst": ["business analyst"],
        "management trainee mba": ["management trainee", "mba trainee", "management trainee mba"],
    }
    return role_keyword_map.get(key, [key])


def _matches_role(title: str, role_queries: List[str] | None = None) -> bool:
    """Check if title matches selected role queries."""
    title_lower = title.lower()
    active_roles = role_queries or ROLE_QUERIES

    for role_name in active_roles:
        keywords = _get_role_keywords(role_name)
        if any(keyword in title_lower for keyword in keywords):
            return True

    return False


def _matches_location(location: str) -> bool:
    """Check if location matches India + allowed regions (Remote/Bangalore/Kolkata)."""
    location_lower = location.lower()

    # Job portals often use "Bengaluru" instead of "Bangalore".
    allowed_location_keywords = ["remote", "bangalore", "bengaluru", "kolkata"]
    has_allowed_location = any(keyword in location_lower for keyword in allowed_location_keywords)
    return has_allowed_location


def _extract_experience_range(experience_text: str) -> tuple[int | None, int | None]:
    """Extract min/max years from text like '0-2 years' or '3+ years'."""
    text = experience_text.lower()

    range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", text)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    plus_match = re.search(r"(\d+)\s*\+", text)
    if plus_match:
        min_years = int(plus_match.group(1))
        return min_years, None

    single_match = re.search(r"\b(\d+)\s*(?:year|years|yr|yrs)\b", text)
    if single_match:
        years = int(single_match.group(1))
        return years, years

    return None, None


def _matches_experience(job: JobListing, experience_level: str) -> bool:
    """Match job to selected experience level bucket."""
    selected = experience_level.lower().strip()
    title_text = job.title.lower()
    exp_text = job.experience.lower()

    fresher_keywords = ["fresher", "freshers", "entry level", "entry-level", "intern", "trainee"]
    senior_keywords = ["senior", "lead", "manager", "principal", "head"]

    has_fresher_hint = any(word in title_text or word in exp_text for word in fresher_keywords)
    has_senior_hint = any(word in title_text for word in senior_keywords)
    min_years, max_years = _extract_experience_range(exp_text)

    if selected == "fresher":
        if has_fresher_hint:
            return True
        return min_years == 0 and (max_years == 0 or max_years is None)

    if selected == "0 to 2 years":
        if has_fresher_hint:
            return False
        if min_years is None and max_years is None:
            return "junior" in title_text or "associate" in title_text
        if min_years is not None and min_years > 2:
            return False
        if max_years is not None and max_years > 2:
            return False
        return True

    if selected == "more experience":
        if has_senior_hint:
            return True
        if min_years is not None and min_years > 2:
            return True
        if max_years is not None and max_years > 2:
            return True
        return False

    return True


def filter_job_listings(
    listings: Iterable[JobListing],
    experience_level: str = "0 to 2 years",
    role_queries: List[str] | None = None,
) -> List[JobListing]:
    """Filter listings based on role, location, and experience requirements."""
    return [
        job
        for job in listings
        if _matches_role(job.title, role_queries=role_queries)
        and _matches_location(job.location)
        and _matches_experience(job, experience_level)
    ]


def build_pdf_table_data(listings: Iterable[JobListing], link_style: ParagraphStyle) -> List[list]:
    """Create table data with header row and clickable apply links."""
    table_data: List[list] = [["Job Title", "Company", "Location", "Experience", "Source", "Apply Link"]]

    for job in listings:
        # Use a Paragraph to render a clickable hyperlink in reportlab.
        link_paragraph = Paragraph(f'<link href="{job.apply_link}">Apply</link>', link_style)
        table_data.append([job.title, job.company, job.location, job.experience, job.source, link_paragraph])

    return table_data


def generate_jobs_pdf(listings: Iterable[JobListing], output_path: Path, fetched_at: datetime) -> None:
    """Generate the final PDF report with a professional table layout."""
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.alignment = 1  # Center
    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["BodyText"],
        alignment=1,
        textColor=colors.HexColor("#34495E"),
        fontSize=10,
    )

    link_style = ParagraphStyle(
        "LinkStyle",
        parent=styles["BodyText"],
        textColor=colors.HexColor("#0B5ED7"),
        underline=True,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title="Daily Job Opportunities",
    )

    story = []
    story.append(Paragraph("Daily Job Opportunities", title_style))
    story.append(
        Paragraph(
            f"Job data fetched on: {fetched_at.strftime('%Y-%m-%d %H:%M:%S')}",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 8 * mm))

    table_data = build_pdf_table_data(listings, link_style)

    # Widths chosen to keep the table readable on A4.
    table = Table(table_data, colWidths=[44 * mm, 28 * mm, 28 * mm, 22 * mm, 16 * mm, 30 * mm], repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F7FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    story.append(table)
    doc.build(story)


def generate_output_filename(base_dir: Path) -> Path:
    """Generate a unique timestamped PDF name for each run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"jobs_{timestamp}.pdf"


def run_pipeline(
    use_mock: bool = False,
    experience_level: str = "0 to 2 years",
    role_queries: List[str] | None = None,
    generate_pdf: bool = True,
    allow_mock_fallback: bool = True,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Run fetching, filtering, and PDF generation and return run metadata."""
    fetched_at = datetime.now()
    active_role_queries = role_queries or ROLE_QUERIES
    used_mock_data = False

    if use_mock:
        all_jobs = collect_mock_job_listings()
        used_mock_data = True
        if progress_callback:
            progress_callback(1, 1, "Loaded mock job data")
    else:
        all_jobs = collect_live_job_listings(
            role_queries=active_role_queries,
            progress_callback=progress_callback,
        )

    if not all_jobs and allow_mock_fallback:
        print("Warning: no live jobs fetched. Falling back to mock data.")
        all_jobs = collect_mock_job_listings()
        used_mock_data = True

    filtered_jobs = filter_job_listings(
        all_jobs,
        experience_level=experience_level,
        role_queries=active_role_queries,
    )

    output_file = None
    if generate_pdf:
        output_file = generate_output_filename(Path(__file__).resolve().parent)
        generate_jobs_pdf(filtered_jobs, output_file, fetched_at)

    return {
        "output_file": output_file,
        "fetched_at": fetched_at,
        "total_fetched": len(all_jobs),
        "total_included": len(filtered_jobs),
        "experience_level": experience_level,
        "role_queries": active_role_queries,
        "jobs": filtered_jobs,
        "used_mock_data": used_mock_data,
    }


def main() -> None:
    """Run data collection, filtering, and PDF generation."""
    parser = argparse.ArgumentParser(description="Generate a daily jobs PDF for analyst roles in India.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock jobs instead of live scraping.",
    )
    parser.add_argument(
        "--experience",
        choices=EXPERIENCE_LEVELS,
        default="0 to 2 years",
        help="Experience filter to apply while selecting jobs.",
    )
    parser.add_argument(
        "--roles",
        nargs="+",
        choices=ROLE_QUERIES + [ALL_ROLES_OPTION],
        default=[ALL_ROLES_OPTION],
        help="Role filters to apply. Use 'All roles' to fetch everything configured.",
    )
    args = parser.parse_args()

    selected_roles = ROLE_QUERIES if ALL_ROLES_OPTION in args.roles else args.roles

    result = run_pipeline(
        use_mock=args.mock,
        experience_level=args.experience,
        role_queries=selected_roles,
    )
    print(f"PDF generated successfully: {result['output_file']}")
    print(f"Job data fetched on: {result['fetched_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Experience filter: {result['experience_level']}")
    print(f"Role filters: {', '.join(result['role_queries'])}")
    print(f"Total jobs fetched: {result['total_fetched']}")
    print(f"Total jobs included: {result['total_included']}")


if __name__ == "__main__":
    main()
