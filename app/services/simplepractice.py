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

# Self-healing selectors: ranked lists of CSS selectors per UI element.
# If the primary selector breaks (SimplePractice UI update), the next one is tried.
# When all fail, a screenshot is saved for debugging.
SELECTORS = {
    "email_input": [
        "#user_email",
        'input[name="user[email]"]',
        'input[type="email"]',
        'input[type="text"][name*="email"]',
    ],
    "password_input": [
        "#user_password",
        'input[name="user[password]"]',
        'input[type="password"]',
    ],
    "login_submit": [
        "#submitBtn",
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Sign in")',
        'button:has-text("Log in")',
    ],
    "ready_for_download": [
        'button:has-text("Ready for download")',
        'button.button-link:has-text("Ready")',
        'button.button-link:has-text("download")',
        'td.is-last-column button',
        '.ember-view button.button-link',
    ],
    "start_export": [
        'button:has-text("Start export")',
        'button:has-text("New export")',
        'a:has-text("Start export")',
        'button.primary:has-text("export")',
    ],
    "all_clients": [
        'text="All clients in the practice"',
        'button:has-text("All clients")',
        'div:has-text("All clients in the practice")',
    ],
    "complete_export": [
        'text="Complete"',
        'label:has-text("Complete")',
        'input[type="radio"][value="complete"]',
        'div:has-text("Includes client contact info and all documentation")',
    ],
    "export_submit": [
        'button:has-text("Export"):not([disabled])',
        'button.primary:has-text("Export"):not([disabled])',
        'button[type="submit"]:has-text("Export")',
    ],
    "swal_dismiss": [
        ".swal2-confirm",
        ".swal2-actions button",
        'button:has-text("OK")',
        'button:has-text("Got it")',
    ],
}


class SimplePracticeExtractor:
    """Extracts patient data from SimplePractice programmatically."""

    def __init__(self, download_dir: str | None = None):
        self._download_dir = download_dir or tempfile.mkdtemp(prefix="sp_export_")
        self._cookies: list[dict] = []

    async def _resilient_find(self, page, element_name: str, timeout: int = 5000):
        """
        Self-healing element finder. Tries each selector in SELECTORS[element_name]
        in order until one matches. If all fail, takes a screenshot for debugging.

        Returns the first matching locator, or raises RuntimeError.
        """
        selectors = SELECTORS.get(element_name, [])
        if not selectors:
            raise ValueError(f"No selectors defined for element: {element_name}")

        for i, selector in enumerate(selectors):
            locator = page.locator(selector)
            try:
                count = await locator.count()
                if count > 0:
                    if i > 0:
                        logger.warning(
                            "Primary selector for '%s' failed. "
                            "Used fallback #%d: %s",
                            element_name, i + 1, selector,
                        )
                    return locator
            except Exception:
                continue

        # All selectors failed — save screenshot for debugging
        screenshot_path = f"/tmp/sp_failed_{element_name}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.error(
            "All %d selectors failed for '%s'. Screenshot: %s. Selectors tried: %s",
            len(selectors), element_name, screenshot_path, selectors,
        )
        raise RuntimeError(
            f"Could not find element '{element_name}' on page {page.url}. "
            f"Tried {len(selectors)} selectors. Screenshot saved to {screenshot_path}"
        )

    async def _resilient_click(self, page, element_name: str, **kwargs):
        """Find element using self-healing selectors and click it."""
        locator = await self._resilient_find(page, element_name)
        await locator.first.click(**kwargs)

    async def _resilient_fill(self, page, element_name: str, value: str):
        """Find element using self-healing selectors and fill it."""
        locator = await self._resilient_find(page, element_name)
        await locator.first.fill(value)

    async def extract(
        self,
        email: str,
        password: str,
        client_name: str | None = None,
        totp_secret: str | None = None,
    ) -> list["PatientExtraction"]:
        """
        Full extraction pipeline: login → export → download → parse ALL clients.

        If client_name is provided, returns only that client.
        If None, discovers and returns all clients in the export.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
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
                export_path = await self._trigger_export(page, client_name or "all")

                # Step 3: Discover all clients and parse each
                if client_name:
                    extraction = self._parse_export(export_path, client_name)
                    return [extraction]
                else:
                    return self._parse_all_clients(export_path)
            finally:
                await browser.close()

    def _discover_clients(self, export_path: Path) -> list[str]:
        """Discover all client names from the export directory structure."""
        clients = set()

        # Check Client records/Medical Records/{Name}/
        for medical_dir in export_path.rglob("Medical Records"):
            if medical_dir.is_dir():
                for child in medical_dir.iterdir():
                    if child.is_dir() and list(child.glob("*.pdf")):
                        clients.add(child.name)

        # Check Psychotherapy Notes/{Name}/
        for psych_dir in export_path.rglob("Psychotherapy Notes"):
            if psych_dir.is_dir():
                for child in psych_dir.iterdir():
                    if child.is_dir() and list(child.glob("*.pdf")):
                        clients.add(child.name)

        logger.info("Discovered %d clients: %s", len(clients), list(clients))
        return sorted(clients)

    def _parse_all_clients(self, export_path: Path) -> list["PatientExtraction"]:
        """Parse all clients found in the export."""
        clients = self._discover_clients(export_path)
        extractions = []

        for client_name in clients:
            try:
                extraction = self._parse_export(export_path, client_name)
                extractions.append(extraction)
                logger.info("Parsed %s: assessment=%d chars, notes=%d",
                            client_name, len(extraction.assessment.raw_text),
                            len(extraction.progress_notes))
            except Exception as e:
                logger.error("Failed to parse client '%s': %s", client_name, e)

        return extractions

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
        await self._resilient_fill(page, "email_input", email)
        await self._resilient_fill(page, "password_input", password)
        await self._resilient_click(page, "login_submit")

        # Wait for SAML redirect back to secure.simplepractice.com
        # The login posts to account.simplepractice.com, which returns a
        # SAMLResponse that redirects to secure.simplepractice.com
        # Poll for up to 45 seconds since SAML can be slow
        for attempt in range(45):
            await page.wait_for_timeout(1000)
            current = page.url
            logger.info("Login redirect check #%d: %s", attempt + 1, current[:80])
            if "secure.simplepractice.com" in current:
                break
            # Check for login error messages
            error_el = page.locator(".alert-danger, .error-message, .flash-error")
            if await error_el.count() > 0:
                error_text = await error_el.first.text_content()
                raise RuntimeError(f"Login error: {error_text}")
        else:
            # Take screenshot for debugging
            await page.screenshot(path="/tmp/sp_login_failed.png", full_page=True)
            raise RuntimeError(
                f"Login failed: SAML redirect did not complete after 45s. "
                f"Current URL: {page.url}. Screenshot: /tmp/sp_login_failed.png"
            )

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

        logger.info("Login successful.")

    async def _trigger_export(self, page, client_name: str) -> Path:
        """
        Navigate to data export page, trigger a single-client export,
        wait for it, and download the ZIP.

        Actual SimplePractice URLs (discovered from live account):
        - Settings: /practice_settings/basic_info
        - Data export: /practice_settings/data_exports
        """
        # Navigate directly to data export page
        logger.info("Navigating to data export page...")
        await page.goto(
            f"{SP_BASE_URL}/practice_settings/data_exports",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        # Wait for the SPA to fully render
        await page.wait_for_timeout(5000)
        logger.info("On data export page: %s", page.url)

        # Dismiss any SweetAlert popups that might be blocking
        try:
            swal_btn = await self._resilient_find(page, "swal_dismiss")
            logger.info("Dismissing popup dialog...")
            await swal_btn.first.click()
            await page.wait_for_timeout(1000)
        except RuntimeError:
            pass  # No popup — continue

        # Count existing "Ready for download" buttons BEFORE triggering new export
        try:
            existing_ready = await self._resilient_find(page, "ready_for_download")
            ready_count_before = await existing_ready.count()
        except RuntimeError:
            ready_count_before = 0
        logger.info("Found %d existing ready exports. Triggering fresh export...", ready_count_before)

        # Step A: Click "Start export"
        logger.info("Clicking 'Start export'...")
        await self._resilient_click(page, "start_export")
        await page.wait_for_timeout(2000)

        # Step B: Click "All clients in the practice"
        logger.info("Selecting 'All clients in the practice'...")
        await self._resilient_click(page, "all_clients")
        await page.wait_for_timeout(2000)

        # Step C: Click "Complete" export type (enables Export button)
        logger.info("Selecting 'Complete' export type...")
        await self._resilient_click(page, "complete_export")
        await page.wait_for_timeout(1000)

        # Step D: Uncheck ALL checkboxes (password protect, etc.)
        logger.info("Unchecking any password/protection checkboxes...")
        checkboxes = page.locator('input[type="checkbox"]')
        count = await checkboxes.count()
        for i in range(count):
            cb = checkboxes.nth(i)
            if await cb.is_checked():
                logger.info("Unchecking checkbox %d", i)
                await cb.uncheck()
                await page.wait_for_timeout(300)
        # Also try clicking any toggle/switch that might be password protection
        password_toggle = page.locator('text="Password protect"').locator('..').locator('input, .toggle, .switch')
        if await password_toggle.count() > 0:
            for i in range(await password_toggle.count()):
                el = password_toggle.nth(i)
                try:
                    if await el.is_checked():
                        await el.uncheck()
                        logger.info("Unchecked password toggle")
                except Exception:
                    pass
        await page.wait_for_timeout(500)

        # Step E: Click "Export"
        logger.info("Clicking 'Export'...")
        export_locator = await self._resilient_find(page, "export_submit")
        await export_locator.last.click(timeout=10000)
        await page.wait_for_timeout(3000)

        # Step F: Poll until there's one MORE "Ready" button than before (= our new export)
        logger.info("Waiting for new export to generate (had %d ready before)...", ready_count_before)
        max_wait = 300
        elapsed = 0
        poll_interval = 10

        while elapsed < max_wait:
            await page.wait_for_timeout(poll_interval * 1000)
            elapsed += poll_interval

            await page.goto(
                f"{SP_BASE_URL}/practice_settings/data_exports",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await page.wait_for_timeout(5000)

            try:
                ready_btn = await self._resilient_find(page, "ready_for_download")
                ready_count_now = await ready_btn.count()
                if ready_count_now > ready_count_before:
                    logger.info("New export ready after %d seconds! (%d -> %d ready)", elapsed, ready_count_before, ready_count_now)
                    # Download the FIRST one (newest, at top of page)
                    return await self._download_export(page, ready_btn.first)
                else:
                    logger.info("Still waiting... %d ready (need > %d) (%ds elapsed)", ready_count_now, ready_count_before, elapsed)
            except RuntimeError:
                logger.info("No ready buttons found (%ds elapsed)...", elapsed)

        raise RuntimeError(f"Export did not complete within {max_wait} seconds")

    async def _download_export(self, page, download_link) -> Path:
        """Click a download link, save the file, and unzip if needed."""
        async with page.expect_download() as download_info:
            await download_link.click()
        download = await download_info.value

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

    def _parse_export(self, export_path: Path, client_name: str) -> PatientExtraction:
        """Parse an exported SimplePractice directory into structured data."""
        # Find ALL directories for this client (Medical Records + Psychotherapy Notes + Stored docs)
        client_dirs = self._find_client_dirs(export_path, client_name)

        if not client_dirs:
            # List what we DID find for debugging
            all_dirs = [str(d) for d in export_path.rglob("*") if d.is_dir()]
            raise RuntimeError(
                f"Could not find records for '{client_name}' in {export_path}. "
                f"Directories found: {all_dirs[:10]}"
            )

        # Collect PDFs from ALL matching directories
        pdf_files = []
        for d in client_dirs:
            pdfs = sorted(d.glob("*.pdf"))
            logger.info("Found %d PDFs in %s", len(pdfs), d)
            pdf_files.extend(pdfs)

        logger.info("Total %d PDF files for %s across %d directories",
                     len(pdf_files), client_name, len(client_dirs))

        assessment = None
        intake_questionnaire = None
        progress_notes: list[ProgressNoteData] = []

        for pdf_path in pdf_files:
            filename = pdf_path.name.lower()
            text = self._extract_pdf_text(pdf_path)

            if not text.strip():
                logger.warning("Empty PDF: %s", pdf_path.name)
                continue

            # Always check content FIRST — SP may label a BPS as "Progress Note"
            text_lower = text[:1000].lower()
            is_bps_content = any(kw in text_lower for kw in [
                "biopsychosocial", "presenting problem", "history of presenting problem",
                "chemical use history", "substance use history", "signs and symptoms",
                "childhood/adolescent history", "counseling/prior treatment",
            ])

            if is_bps_content and not assessment:
                # This is a BPS regardless of filename
                logger.info("Detected BPS assessment by content: %s", pdf_path.name)
                assessment = self._parse_assessment_pdf(text, pdf_path.name)
            elif "biopsychosocial" in filename or ("assessment" in filename and "questionnaire" not in filename):
                if not assessment:
                    assessment = self._parse_assessment_pdf(text, pdf_path.name)
            elif "questionnaire" in filename or "intake" in filename:
                intake_questionnaire = text
            elif "progress note" in filename or "psychotherapy note" in filename or "chart note" in filename:
                note = self._parse_progress_note_pdf(text, pdf_path.name)
                if note:
                    progress_notes.append(note)
            else:
                # Check content for SOAP/DAP patterns
                if any(kw in text_lower for kw in ["subjective", "objective", "plan"]):
                    logger.info("Detected progress note by content: %s", pdf_path.name)
                    note = self._parse_progress_note_pdf(text, pdf_path.name)
                    if note:
                        progress_notes.append(note)
                else:
                    logger.warning("Could not classify PDF: %s — treating as supplemental", pdf_path.name)
                    if not intake_questionnaire:
                        intake_questionnaire = text

        # Collect all raw text for demographics extraction
        all_raw_texts = []
        for pdf_path in pdf_files:
            text = self._extract_pdf_text(pdf_path)
            if text.strip():
                all_raw_texts.append(text)

        # Extract demographics from all available text
        demographics = self._extract_demographics(
            assessment, intake_questionnaire, client_name, all_raw_texts
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

        # If no BPS found by filename or content, try using the longest PDF as assessment
        if not assessment:
            all_texts = []
            for pdf_path in pdf_files:
                text = self._extract_pdf_text(pdf_path)
                if text.strip():
                    all_texts.append((pdf_path, text))
            if all_texts:
                # Use the longest document as the assessment
                longest = max(all_texts, key=lambda x: len(x[1]))
                logger.warning(
                    "No BPS found by name/content — using longest PDF as assessment: %s (%d chars)",
                    longest[0].name, len(longest[1]),
                )
                assessment = self._parse_assessment_pdf(longest[1], longest[0].name)
            else:
                raise RuntimeError("No BPS assessment found in export — no PDFs contain clinical content")

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

    def _find_client_dirs(self, export_path: Path, client_name: str) -> list[Path]:
        """Find ALL directories for this client in the export.

        SimplePractice splits files across multiple locations:
        - Client records/Medical Records/{Name}/  (progress notes, assessments, questionnaires)
        - Psychotherapy Notes/{Name}/  (psychotherapy notes, separate per HIPAA)
        - Client records/Stored documents/{Name}/  (consent forms, etc.)
        """
        dirs = []
        name_lower = client_name.lower()

        # Find all directories matching client name
        for dirpath in export_path.rglob("*"):
            if dirpath.is_dir() and name_lower in dirpath.name.lower():
                # Only include dirs that have PDFs
                if list(dirpath.glob("*.pdf")):
                    dirs.append(dirpath)
                    logger.info("Found client directory: %s (%d PDFs)",
                                dirpath, len(list(dirpath.glob("*.pdf"))))

        if dirs:
            return dirs

        # Fallback: look for any directory with PDFs
        logger.warning("No directory matching '%s' found — searching all PDF directories", client_name)
        for dirpath in export_path.rglob("*"):
            if dirpath.is_dir() and list(dirpath.glob("*.pdf")):
                # Skip billing/invoice directories
                if "billing" not in str(dirpath).lower() and "invoice" not in str(dirpath).lower():
                    dirs.append(dirpath)

        return dirs

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
        all_texts: list[str] | None = None,
    ) -> PatientDemographics:
        """Extract patient demographics from available data.

        Searches ALL available text (assessment, intake, progress notes)
        for demographics since SP may label the BPS as a progress note.
        """
        name_parts = client_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else client_name
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Search all available text for DOB
        dob = date(2000, 1, 1)
        search_texts = []
        if assessment:
            search_texts.append(assessment.raw_text)
        if intake_text:
            search_texts.append(intake_text)
        if all_texts:
            search_texts.extend(all_texts)

        for text in search_texts:
            dob_match = re.search(r"DOB:\s*(\d{2}/\d{2}/\d{4})", text)
            if dob_match:
                try:
                    dob = datetime.strptime(dob_match.group(1), "%m/%d/%Y").date()
                    break
                except ValueError:
                    continue

        # Search all text for gender
        gender = "Unknown"
        for text in search_texts:
            # Look for explicit age-gender pattern first (e.g., "37-year-old female")
            age_gender = re.search(r"\d+-year-old\s+(male|female)", text.lower())
            if age_gender:
                gender = age_gender.group(1).capitalize()
                break
            # Look for Sex/Gender field
            sex_match = re.search(r"(?:Sex|Gender):\s*(Male|Female|M|F)", text, re.IGNORECASE)
            if sex_match:
                val = sex_match.group(1).upper()
                gender = "Male" if val in ("M", "MALE") else "Female"
                break

        if gender == "Unknown":
            gender = self._extract_gender(assessment, intake_text)

        # Try to find admission date from text
        admission = date.today()
        for text in search_texts:
            admit_match = re.search(r"(?:Admission|Admitted|admission date)[:\s]*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
            if admit_match:
                try:
                    admission = datetime.strptime(admit_match.group(1), "%m/%d/%Y").date()
                    break
                except ValueError:
                    continue

        return PatientDemographics(
            id=client_name.lower().replace(" ", "_"),
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=gender,
            primary_language="English",
            admission_date=admission,
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
