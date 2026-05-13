"""
SimplePractice Data Extraction Service

Programmatically extracts patient data from SimplePractice by:
1. Logging in via Playwright (headless browser automation)
2. Triggering the built-in data export for a specific client
3. Downloading the exported ZIP
4. Parsing CSVs (demographics) and PDFs (clinical notes) with pdfplumber

SimplePractice has no public API. This is the same approach used by healthcare
data companies like Datavant — browser automation ("web-based login").

In production, this runs inside a Docker container / cloud VM for isolation.
For this prototype, it runs locally with headless Chromium.

Architecture:
- account.simplepractice.com — SAML Identity Provider (Rails 7 + Devise)
- secure.simplepractice.com — Practice app (Ember.js SPA)
- Login uses SAML SSO redirect chain (Playwright follows automatically)
- No CAPTCHA on login; Sift Science passive behavioral analytics only
"""

import csv
import io
import logging
import os
import re
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pdfplumber
from playwright.async_api import async_playwright

from app.schemas.patient import (
    AssessmentData,
    ClinicianInfo,
    Diagnosis,
    ExtractionMetadata,
    PatientDemographics,
    PatientExtraction,
    ProgressNoteData,
)

logger = logging.getLogger(__name__)

SP_LOGIN_URL = "https://secure.simplepractice.com/users/sign_in"
SP_BASE_URL = "https://secure.simplepractice.com"


class SimplePracticeExtractor:
    """Extracts patient data from SimplePractice programmatically."""

    def __init__(self, download_dir: str | None = None):
        self._download_dir = download_dir or tempfile.mkdtemp(prefix="sp_export_")
        self._cookies: list[dict] = []

    async def extract(
        self,
        email: str,
        password: str,
        client_name: str,
        totp_secret: str | None = None,
    ) -> PatientExtraction:
        """
        Full extraction pipeline: login → export → download → parse.

        Args:
            email: SimplePractice admin email
            password: SimplePractice admin password
            client_name: Name of the client to export (e.g. "Jack Smith")
            totp_secret: Optional TOTP secret for 2FA
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                accept_downloads=True,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                # Step 1: Log in
                await self._login(page, email, password, totp_secret)

                # Step 2: Navigate to data export and trigger export
                export_path = await self._trigger_export(page, client_name)

                # Step 3: Parse the exported files
                extraction = self._parse_export(export_path, client_name)

                return extraction
            finally:
                await browser.close()

    async def _login(
        self,
        page,
        email: str,
        password: str,
        totp_secret: str | None = None,
    ) -> None:
        """Log into SimplePractice via SAML SSO redirect chain."""
        logger.info("Navigating to SimplePractice login...")
        await page.goto(SP_LOGIN_URL, wait_until="networkidle")
        logger.info("Login page: %s", page.url)

        # Fill credentials on account.simplepractice.com
        await page.fill(
            'input[type="email"], input[name="email"], #email, input[name="account[email]"]',
            email,
        )
        await page.fill(
            'input[type="password"], input[name="password"], #password, input[name="account[password]"]',
            password,
        )
        await page.click('button[type="submit"], input[type="submit"]')
        await page.wait_for_load_state("networkidle", timeout=30000)

        # Handle 2FA if needed
        if "verification" in page.url.lower() or "two_factor" in page.url.lower():
            if totp_secret:
                import pyotp

                code = pyotp.TOTP(totp_secret).now()
                await page.fill('input[name="code"], input[type="tel"]', code)
                await page.click('button[type="submit"]')
                await page.wait_for_load_state("networkidle", timeout=15000)
            else:
                raise RuntimeError(
                    "2FA required but no totp_secret provided. "
                    "Disable 2FA or provide the TOTP secret."
                )

        # Verify login succeeded
        if "secure.simplepractice.com" not in page.url:
            raise RuntimeError(f"Login failed. Current URL: {page.url}")

        logger.info("Login successful.")

    async def _trigger_export(self, page, client_name: str) -> Path:
        """
        Navigate to Settings > Practice > Data export, trigger a single-client
        export, wait for it, and download the ZIP.
        """
        # Navigate to data export page
        logger.info("Navigating to data export settings...")
        await page.goto(f"{SP_BASE_URL}/settings", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Click through to Data Export
        # SimplePractice settings has sections — look for "Practice" then "Data export"
        export_link = page.locator('a:has-text("Data export"), a:has-text("Data Export")')
        if await export_link.count() > 0:
            await export_link.first.click()
            await page.wait_for_load_state("networkidle")
        else:
            # Try direct URL
            await page.goto(
                f"{SP_BASE_URL}/settings/practice/data-export",
                wait_until="networkidle",
            )

        await page.wait_for_timeout(2000)
        logger.info("On data export page: %s", page.url)

        # Click "Start export" or "New export" button
        start_btn = page.locator(
            'button:has-text("Start export"), '
            'button:has-text("New export"), '
            'a:has-text("Start export"), '
            'button:has-text("Export")'
        )
        if await start_btn.count() > 0:
            await start_btn.first.click()
            await page.wait_for_timeout(2000)

        # Select "One client" scope
        one_client = page.locator(
            'label:has-text("One client"), '
            'input[value="one_client"], '
            'label:has-text("one client"), '
            'div:has-text("One client")'
        )
        if await one_client.count() > 0:
            await one_client.first.click()
            await page.wait_for_timeout(1000)

        # Search for and select the client
        client_search = page.locator(
            'input[placeholder*="client"], '
            'input[placeholder*="Client"], '
            'input[placeholder*="Search"], '
            'input[type="search"]'
        )
        if await client_search.count() > 0:
            await client_search.first.fill(client_name)
            await page.wait_for_timeout(1500)
            # Click the matching result
            result = page.locator(f'text="{client_name}"')
            if await result.count() > 0:
                await result.first.click()
                await page.wait_for_timeout(500)

        # Select "Sessions" or "Complete" export type
        sessions_option = page.locator(
            'label:has-text("Sessions"), '
            'label:has-text("Complete"), '
            'input[value="sessions"]'
        )
        if await sessions_option.count() > 0:
            await sessions_option.first.click()
            await page.wait_for_timeout(500)

        # Click the export/submit button
        submit_btn = page.locator(
            'button:has-text("Export"), '
            'button:has-text("Start"), '
            'button[type="submit"]'
        )
        if await submit_btn.count() > 0:
            await submit_btn.first.click()

        # Wait for export to generate — poll the page for "Ready for download"
        logger.info("Waiting for export to generate...")
        max_wait = 300  # 5 minutes max
        elapsed = 0
        poll_interval = 10

        while elapsed < max_wait:
            await page.wait_for_timeout(poll_interval * 1000)
            elapsed += poll_interval

            # Refresh the page to check status
            await page.reload(wait_until="networkidle")

            # Look for download link
            download_link = page.locator(
                'a:has-text("Download"), '
                'a:has-text("Ready"), '
                'button:has-text("Download")'
            )
            if await download_link.count() > 0:
                logger.info("Export ready after %d seconds.", elapsed)

                # Click download and capture the file
                async with page.expect_download() as download_info:
                    await download_link.first.click()
                download = await download_info.value

                # Save to our download directory
                save_path = os.path.join(self._download_dir, download.suggested_filename)
                await download.save_as(save_path)
                logger.info("Downloaded export to: %s", save_path)

                # Unzip if it's a ZIP
                if save_path.endswith(".zip"):
                    extract_dir = save_path.replace(".zip", "")
                    with zipfile.ZipFile(save_path, "r") as zf:
                        zf.extractall(extract_dir)
                    return Path(extract_dir)

                return Path(save_path)

            logger.info("Export not ready yet (%ds elapsed)...", elapsed)

        raise RuntimeError(f"Export did not complete within {max_wait} seconds")

    def _parse_export(self, export_path: Path, client_name: str) -> PatientExtraction:
        """Parse an exported SimplePractice directory into structured data."""
        # Find the client's records directory
        records_dir = self._find_client_dir(export_path, client_name)

        if not records_dir:
            raise RuntimeError(
                f"Could not find records for '{client_name}' in {export_path}"
            )

        # Parse all PDFs in the directory
        pdf_files = sorted(records_dir.glob("*.pdf"))
        logger.info("Found %d PDF files for %s", len(pdf_files), client_name)

        assessment = None
        intake_questionnaire = None
        progress_notes: list[ProgressNoteData] = []

        for pdf_path in pdf_files:
            filename = pdf_path.name.lower()
            text = self._extract_pdf_text(pdf_path)

            if not text.strip():
                logger.warning("Empty PDF: %s", pdf_path.name)
                continue

            if "biopsychosocial" in filename or "assessment" in filename:
                assessment = self._parse_assessment_pdf(text, pdf_path.name)
            elif "questionnaire" in filename or "intake" in filename:
                intake_questionnaire = text
            elif "progress note" in filename:
                note = self._parse_progress_note_pdf(text, pdf_path.name)
                if note:
                    progress_notes.append(note)

        # Extract demographics from BPS header or intake questionnaire
        demographics = self._extract_demographics(
            assessment, intake_questionnaire, client_name
        )

        # If we have an intake questionnaire, append it to the assessment raw text
        if assessment and intake_questionnaire:
            assessment = AssessmentData(
                **{
                    **assessment.model_dump(),
                    "raw_text": assessment.raw_text
                    + "\n\n=== INTAKE QUESTIONNAIRE ===\n"
                    + intake_questionnaire,
                }
            )

        if not assessment:
            raise RuntimeError("No BPS assessment found in export")

        progress_notes.sort(key=lambda n: n.note_date)

        return PatientExtraction(
            patient=demographics,
            assessment=assessment,
            progress_notes=progress_notes,
            extraction_metadata=ExtractionMetadata(
                source="simplepractice_export",
                extracted_at=datetime.now(timezone.utc),
            ),
        )

    def _find_client_dir(self, export_path: Path, client_name: str) -> Path | None:
        """Find the client's records directory in the export."""
        # SimplePractice export structure:
        # Export.../Client records/Medical Records/Jack Smith/
        for dirpath in export_path.rglob("*"):
            if dirpath.is_dir() and client_name.lower() in dirpath.name.lower():
                return dirpath

        # Fallback: look for any directory with PDFs
        for dirpath in export_path.rglob("*"):
            if dirpath.is_dir() and list(dirpath.glob("*.pdf")):
                return dirpath

        return None

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract all text from a PDF using pdfplumber."""
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    def _parse_assessment_pdf(self, text: str, filename: str) -> AssessmentData:
        """Parse a BPS assessment PDF into structured AssessmentData."""
        # Extract clinician info from header
        clinician_name = self._extract_field(text, r"Provider:\s*(.+)")
        dob = self._extract_field(text, r"DOB:\s*(\d{2}/\d{2}/\d{4})")

        return AssessmentData(
            assessment_type="biopsychosocial_intake",
            assessment_date=self._extract_date_from_filename(filename),
            clinician=ClinicianInfo(
                name=clinician_name or "Unknown",
                credentials="",
            ),
            presenting_problem=self._extract_section(
                text, ["1. Presenting Problem", "Presenting Problem"]
            ),
            history_of_present_illness=self._extract_section(
                text, ["3. History of Presenting Problem", "History of Presenting Problem"]
            ),
            substance_use_history=self._extract_section(
                text, ["15. Chemical Use History", "Chemical Use History", "Substance"]
            ),
            medical_history=self._extract_section(
                text, ["14. Physical Health", "Physical Health"]
            ),
            psychiatric_history=self._extract_section(
                text, ["16. Counseling/Prior Treatment", "Prior Treatment"]
            ),
            family_history=self._extract_section(
                text,
                [
                    "Family mental health history",
                    "4. Current Family",
                    "Current Family and Significant Relationships",
                ],
            ),
            social_history=self._extract_section(
                text, ["6. Social Relationships", "Social Relationships"]
            ),
            spiritual_cultural=self._extract_section(
                text,
                [
                    "8. Spiritual/Religious",
                    "Spiritual/Religious",
                    "7. Cultural/Ethnic",
                    "Cultural/Ethnic",
                ],
            ),
            strengths=self._extract_strengths(text),
            risk_assessment=self._extract_section(
                text, ["suicidal", "risk", "Signs and Symptoms"]
            ),
            mental_status_exam=self._extract_section(
                text, ["Mental Status", "MSE"]
            ),
            diagnoses=self._extract_diagnoses(text),
            raw_text=text,
        )

    def _parse_progress_note_pdf(
        self, text: str, filename: str
    ) -> ProgressNoteData | None:
        """Parse a progress note PDF into structured ProgressNoteData."""
        # Detect note format
        note_format = "SOAP"  # default
        if "DSAP" in text[:200]:
            note_format = "DSAP"
        elif "DAP Note" in text[:200]:
            note_format = "DAP"
        elif "SOAP Note" in text[:200]:
            note_format = "SOAP"

        # Extract sections based on format
        sections = self._extract_note_sections(text, note_format)

        # Extract metadata from header
        clinician_name = self._extract_field(text, r"Provider:\s*(.+)")
        note_date = self._extract_date_from_filename(filename)

        # Try to get date from the appointment line
        appt_date = self._extract_field(
            text, r"(?:Individual|Group) appointment on (\w+ \d+, \d{4})"
        )
        if appt_date:
            try:
                note_date = datetime.strptime(appt_date, "%B %d, %Y").date()
            except ValueError:
                pass

        # Extract duration
        duration_match = re.search(r"(\d+)\s*min", text[:300])
        duration = int(duration_match.group(1)) if duration_match else None

        # Extract CPT code
        cpt_match = re.search(r"Billing code:\s*(\d{5})", text[:300])
        cpt_code = cpt_match.group(1) if cpt_match else None

        return ProgressNoteData(
            note_date=note_date,
            note_format=note_format,
            clinician=ClinicianInfo(
                name=clinician_name or "Unknown",
                credentials="",
            ),
            sections=sections,
            raw_text=text,
            session_duration_minutes=duration,
            cpt_code=cpt_code,
        )

    def _extract_note_sections(self, text: str, note_format: str) -> dict[str, str]:
        """Extract sections from a progress note based on its format."""
        sections = {}

        if note_format == "SOAP":
            sections["subjective"] = self._extract_section(text, ["Subjective"])
            sections["objective"] = self._extract_section(text, ["Objective"])
            sections["assessment"] = self._extract_section(text, ["Assessment"])
            sections["plan"] = self._extract_section(text, ["Plan"])
        elif note_format == "DAP":
            sections["data"] = self._extract_section(text, ["Data"])
            sections["assessment"] = self._extract_section(
                text, ["Assessment and Response", "Assessment"]
            )
            sections["plan"] = self._extract_section(text, ["Plan"])
        elif note_format == "DSAP":
            sections["data"] = self._extract_section(text, ["Data"])
            sections["subjective"] = self._extract_section(text, ["Subjective"])
            sections["assessment"] = self._extract_section(text, ["Assessment"])
            sections["plan"] = self._extract_section(text, ["Plan"])

        return sections

    def _extract_demographics(
        self,
        assessment: AssessmentData | None,
        intake_text: str | None,
        client_name: str,
    ) -> PatientDemographics:
        """Extract patient demographics from available data."""
        name_parts = client_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else client_name
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Try to get DOB from assessment
        dob = date(2000, 1, 1)
        if assessment:
            dob_match = re.search(r"DOB:\s*(\d{2}/\d{2}/\d{4})", assessment.raw_text)
            if dob_match:
                try:
                    dob = datetime.strptime(dob_match.group(1), "%m/%d/%Y").date()
                except ValueError:
                    pass

        return PatientDemographics(
            id=client_name.lower().replace(" ", "_"),
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=self._extract_gender(assessment, intake_text),
            primary_language="English",
            admission_date=date.today(),
            diagnoses=assessment.diagnoses if assessment else [],
        )

    def _extract_gender(
        self, assessment: AssessmentData | None, intake_text: str | None
    ) -> str:
        """Try to extract gender from available text."""
        for text in [
            assessment.raw_text if assessment else "",
            intake_text or "",
        ]:
            if not text:
                continue
            # Look for pronouns
            he_count = len(re.findall(r"\bhe\b|\bhis\b|\bhim\b", text.lower()))
            she_count = len(re.findall(r"\bshe\b|\bher\b|\bhers\b", text.lower()))
            if he_count > she_count + 3:
                return "Male"
            if she_count > he_count + 3:
                return "Female"
        return "Unknown"

    def _extract_section(self, text: str, headers: list[str]) -> str:
        """Extract a section of text that starts with one of the given headers."""
        lines = text.split("\n")

        # Known section headers in SimplePractice BPS and progress notes
        all_section_headers = {
            "subjective", "objective", "assessment", "plan",
            "data", "assessment and response",
            "presenting problem", "signs and symptoms",
            "history of presenting problem", "current family",
            "childhood/adolescent history", "social relationships",
            "cultural/ethnic", "spiritual/religious", "legal",
            "education", "employment/vocational", "military",
            "leisure/recreational", "physical health",
            "chemical use history", "counseling/prior treatment",
        }

        for header in headers:
            header_lower = header.lower()
            capturing = False
            captured = []

            for line in lines:
                line_stripped = line.strip()
                line_lower = line_stripped.lower()

                # Check if this line IS the header we're looking for
                if header_lower in line_lower and not capturing:
                    capturing = True
                    # If header and content are on the same line (after a colon)
                    if ":" in line_stripped:
                        remainder = line_stripped.split(":", 1)[1].strip()
                        if remainder:
                            captured.append(remainder)
                    continue

                if capturing:
                    # Stop at page footer
                    if "Created on" in line_stripped and "Page" in line_stripped:
                        break

                    # Stop at a BPS numbered section header (e.g., "5. Childhood/Adolescent History")
                    num_header_match = re.match(r"^(\d+)\.\s+(.+)", line_stripped)
                    if num_header_match:
                        section_name = num_header_match.group(2).strip().rstrip(":")
                        if section_name.lower() in all_section_headers:
                            break

                    # Stop at a progress note section header (bold standalone word like "Subjective" or "Plan")
                    clean = line_stripped.rstrip(":")
                    if (
                        clean
                        and clean[0].isupper()
                        and len(clean) < 40
                        and clean.lower() in all_section_headers
                        and clean.lower() != header_lower
                    ):
                        break

                    captured.append(line_stripped)

            result = "\n".join(captured).strip()
            if result:
                return result

        return "Not documented"

    def _extract_strengths(self, text: str) -> str:
        """Extract strengths from multiple sections of the BPS."""
        strengths = []
        for header in [
            "Strengths/support",
            "Strengths:",
            "strengths",
        ]:
            section = self._extract_section(text, [header])
            if section and section != "Not documented":
                strengths.append(section)

        return "\n".join(strengths) if strengths else "Not documented"

    def _extract_diagnoses(self, text: str) -> list[Diagnosis]:
        """Extract ICD-10 diagnosis codes from text."""
        diagnoses = []
        # Look for ICD-10 patterns (F10.20, F33.1, etc.)
        icd_pattern = r"[A-Z]\d{2}\.\d{1,2}"
        matches = re.findall(icd_pattern, text)
        for code in set(matches):
            diagnoses.append(Diagnosis(code=code, description=""))
        return diagnoses

    @staticmethod
    def _extract_field(text: str, pattern: str) -> str | None:
        """Extract a single field using a regex pattern."""
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_date_from_filename(filename: str) -> date:
        """Extract a date from a SimplePractice export filename."""
        # Pattern: "Progress Note 2026-05-07 154500 928187158.pdf"
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if date_match:
            try:
                return datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass
        return date.today()


class LocalExportParser(SimplePracticeExtractor):
    """
    Parse an already-downloaded SimplePractice export directory.

    Use this when you already have the export on disk (e.g., during development)
    instead of automating the full login → export → download flow.
    """

    def parse_directory(self, export_path: str, client_name: str) -> PatientExtraction:
        """Parse an export directory that's already on disk."""
        return self._parse_export(Path(export_path), client_name)
