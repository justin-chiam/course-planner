import json
import re
from datetime import date

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .normalise import (
    COURSE_CODE_PATTERN,
    SUBJECT_CODE_PATTERN,
    clean_text,
    classify_faculty,
    format_section_lines,
    get_handbook_level,
    validate_course_code,
    validate_subject_code,
)

YEAR = date.today().year
HANDBOOK = "https://www.handbook.unsw.edu.au"


class SubjectArea:
    def __init__(self, code, name, offered_by, faculty, url):
        self.code = code
        self.name = name
        self.offered_by = offered_by
        self.faculty = faculty
        self.url = url


class Course:
    def __init__(
        self,
        code,
        title,
        uoc,
        url,
        subject=None,
        year=None,
        faculty=None,
        school=None,
        terms=None,
    ):
        self.code = code
        self.title = title
        self.uoc = uoc
        self.url = url
        self.subject = subject
        self.year = year
        self.faculty = faculty
        self.school = school
        self.terms = terms or []


EXTRACT_HANDBOOK_SECTION_JS = """
(startHeadings) => {
    const cleanHeading = (text) => text
        .split("\\n")[0]
        .replace(/\\s+/g, " ")
        .trim()
        .toLowerCase();
    const wanted = new Set(startHeadings.map(cleanHeading));

    for (const heading of document.querySelectorAll("h3")) {
        if (!wanted.has(cleanHeading(heading.innerText))) {
            continue;
        }

        const card = heading.parentElement?.parentElement;
        if (!card) {
            continue;
        }

        const lines = card.innerText
            .split("\\n")
            .map((line) => line.trim())
            .filter(Boolean);

        if (lines.length && wanted.has(cleanHeading(lines[0]))) {
            lines.shift();
        }

        return lines.join("\\n");
    }

    return null;
}
"""


def get_timetable_base(year=YEAR):
    return f"https://timetable.unsw.edu.au/{year}"


def get_timetable_url(course_code, year=YEAR):
    course_code = validate_course_code(course_code)
    return f"{get_timetable_base(year)}/{course_code}.html"


def get_handbook_url(course_code, level=None, year=YEAR):
    course_code = validate_course_code(course_code)
    if level is None:
        level = get_handbook_level(course_code)
    return f"{HANDBOOK}/{level}/courses/{year}/{course_code}"


def fetch_soup(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_subject_areas(year=YEAR):
    soup = fetch_soup(f"{get_timetable_base(year)}/subjectSearch.html")
    subjects = []

    for row in soup.find_all("tr"):
        cells = [
            clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")
        ]
        if len(cells) < 3:
            continue

        links = row.find_all("a", href=True)
        if not links:
            continue

        code = clean_text(links[0].get_text(" ", strip=True))
        if not re.fullmatch(SUBJECT_CODE_PATTERN, code):
            continue

        href = links[0]["href"]
        if ".html" not in href:
            continue

        name = (
            clean_text(links[1].get_text(" ", strip=True))
            if len(links) > 1
            else cells[1]
        )
        offered_by = cells[-1]
        url = f"{get_timetable_base(year)}/{href}"
        faculty = classify_faculty(offered_by)

        subjects.append(SubjectArea(code, name, offered_by, faculty, url))

    return subjects


def find_subject_area(subject_code, year=YEAR):
    subject_code = validate_subject_code(subject_code)
    subjects = extract_subject_areas(year)

    for subject in subjects:
        if subject.code == subject_code:
            return subject

    raise ValueError(f"Subject area {subject_code} was not found.")


def extract_courses(subject, level="Undergraduate", year=YEAR):
    soup = fetch_soup(subject.url)
    courses = []
    in_level_section = False

    for row in soup.find_all("tr"):
        text = clean_text(row.get_text(" ", strip=True))

        if text == level:
            in_level_section = True
            continue

        if text in ["Undergraduate", "Postgraduate", "Research"] and text != level:
            in_level_section = False
            continue

        if not in_level_section:
            continue

        cells = [
            clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")
        ]
        if len(cells) < 3:
            continue

        links = row.find_all("a", href=True)
        if not links:
            continue

        code = clean_text(links[0].get_text(" ", strip=True))
        if not re.fullmatch(COURSE_CODE_PATTERN, code):
            continue

        title = (
            clean_text(links[1].get_text(" ", strip=True))
            if len(links) > 1
            else cells[1]
        )
        uoc = cells[-1]
        if not uoc.isdigit():
            continue

        url = f"{get_timetable_base(year)}/{links[0]['href']}"
        courses.append(
            Course(
                code,
                title,
                int(uoc),
                url,
                subject.code,
                year,
                subject.faculty,
                subject.offered_by,
            )
        )

    return courses


def extract_subject_courses(subject_code, level="Undergraduate", year=YEAR):
    subject = find_subject_area(subject_code, year)
    return extract_courses(subject, level, year)


def find_course(course_code, year=YEAR):
    course_code = validate_course_code(course_code)
    subject = find_subject_area(course_code[:4], year)

    for level in ["Undergraduate", "Postgraduate", "Research"]:
        courses = extract_courses(subject, level, year)
        for course in courses:
            if course.code == course_code:
                return course

    return None


def get_line_after_label(lines, label):
    for index, line in enumerate(lines):
        if line == label and index + 1 < len(lines):
            return lines[index + 1]
    return None


def extract_terms_from_timetable_lines(lines):
    terms = []
    in_offering_table = False

    for line in lines:
        if line == "Teaching Period":
            in_offering_table = True
            continue

        if in_offering_table and line.startswith("SUMMARY"):
            break

        if in_offering_table and re.fullmatch(r"[A-Z]\d", line):
            if line not in terms:
                terms.append(line)

    return terms


def extract_timetable_details(course_code, year=YEAR):
    soup = fetch_soup(get_timetable_url(course_code, year))
    lines = [
        clean_text(line)
        for line in soup.get_text("\n").splitlines()
        if clean_text(line)
    ]

    faculty = get_line_after_label(lines, "Faculty")

    return {
        "faculty": classify_faculty(faculty or ""),
        "school": get_line_after_label(lines, "School"),
        "terms": extract_terms_from_timetable_lines(lines),
    }


def html_to_text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    lines = []

    for element in soup.find_all(["p", "li"]):
        text = clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if element.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)

    if lines:
        return "\n".join(lines)

    return clean_text(soup.get_text(" ", strip=True))


def extract_handbook_details_from_html(course_code, level=None, year=YEAR):
    course_code = validate_course_code(course_code)
    handbook_url = get_handbook_url(course_code, level, year)
    soup = fetch_soup(handbook_url)
    next_data = soup.find("script", id="__NEXT_DATA__")

    if not next_data or not next_data.string:
        return None

    try:
        data = json.loads(next_data.string)
    except json.JSONDecodeError:
        return None

    page_content = data.get("props", {}).get("pageProps", {}).get("pageContent", {})
    if not page_content:
        return None

    title = clean_text(page_content.get("title", course_code))
    overview = html_to_text(
        page_content.get("overview") or page_content.get("description") or ""
    )

    conditions = []
    for rule in page_content.get("enrolment_rules", []):
        description = html_to_text(rule.get("description", ""))
        if description:
            conditions.append(description)

    return (
        handbook_url,
        title,
        overview or "Overview not found on Handbook page.",
        "\n".join(conditions) or "No conditions for enrolment found on Handbook page.",
    )


def expand_handbook_content(page):
    for _ in range(5):
        read_more = page.get_by_text("Read More", exact=True).first
        try:
            if read_more.count() == 0 or not read_more.is_visible(timeout=1000):
                break
            read_more.click(timeout=3000)
            page.wait_for_timeout(300)
        except Exception:
            break


def extract_section(page, start_headings):
    section_text = page.evaluate(EXTRACT_HANDBOOK_SECTION_JS, start_headings)
    if not section_text:
        return None

    section_lines = [
        line.strip()
        for line in section_text.splitlines()
        if line.strip()
        and "For more content click the Read More button below" not in line
        and line.strip() != "Read More"
        and not line.strip().lower().startswith("about ")
    ]

    cleaned_lines = [clean_text(line) for line in section_lines]
    formatted_lines = format_section_lines(cleaned_lines)
    result = "\n".join(formatted_lines)
    return result if result else None


def extract_handbook_details(course_code, level=None, year=YEAR):
    course_code = validate_course_code(course_code)
    if level is None:
        level = get_handbook_level(course_code)

    handbook_url = get_handbook_url(course_code, level, year)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(handbook_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)

                if page.title().startswith("ERROR:"):
                    raise RuntimeError("Handbook blocked the browser request.")

                expand_handbook_content(page)

                title = clean_text(page.locator("h2").first.inner_text(timeout=30000))
                overview = extract_section(page, ["Overview"])
                conditions = extract_section(page, ["Conditions for Enrolment"])
            finally:
                browser.close()
    except Exception:
        fallback = extract_handbook_details_from_html(course_code, level, year)
        if fallback:
            return fallback
        raise

    if not overview:
        overview = "Overview not found on Handbook page."

    if not conditions:
        conditions = "No conditions for enrolment found on Handbook page."

    return handbook_url, title, overview, conditions


def course_to_dict(course):
    return {
        "code": course.code,
        "title": course.title,
        "uoc": course.uoc,
        "subject": course.subject,
        "level": int(course.code[4]),
        "faculty": course.faculty,
        "school": course.school,
        "year": course.year,
        "timetableUrl": course.url,
        "terms": course.terms,
    }


def course_details_to_dict(
    course_code,
    year=YEAR,
    timetable_url=None,
    uoc=None,
    faculty=None,
    school=None,
    terms=None,
):
    course_code = validate_course_code(course_code)
    level = get_handbook_level(course_code)
    course = None
    if uoc is None or faculty is None or school is None:
        course = find_course(course_code, year)
    timetable_details = None
    if faculty is None or school is None or terms is None:
        timetable_details = extract_timetable_details(course_code, year)

    if course:
        if uoc is None:
            uoc = course.uoc
        if faculty is None:
            faculty = course.faculty
        if school is None:
            school = course.school

    if faculty is None and timetable_details:
        faculty = timetable_details["faculty"]
    if school is None and timetable_details:
        school = timetable_details["school"]
    if terms is None and timetable_details:
        terms = timetable_details["terms"]

    handbook_url, title, overview, conditions = extract_handbook_details(
        course_code, level, year
    )

    return {
        "code": course_code,
        "title": title,
        "subject": course_code[:4],
        "level": int(course_code[4]),
        "uoc": uoc,
        "faculty": faculty,
        "school": school,
        "year": year,
        "timetableUrl": timetable_url or get_timetable_url(course_code, year),
        "handbookUrl": handbook_url,
        "description": overview,
        "enrolmentConditions": conditions,
        "terms": terms or [],
    }
