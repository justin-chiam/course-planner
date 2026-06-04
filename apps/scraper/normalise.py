import re

COURSE_CODE_PATTERN = r"[A-Z]{4}\d{4}"
SUBJECT_CODE_PATTERN = r"[A-Z]{4}"


FACULTIES = {
    "Arts, Design & Architecture": [
        "Architectural Studies Program",
        "Building Construction Mgt Prog",
        "Faculty of Arts, Design & Arch",
        "Industrial Design Program",
        "Interior Architecture Program",
        "Landscape Architecture Program",
        "Linguistics",
        "Planning & Urban Development",
        "School Humanities & Languages",
        "School of Art & Design",
        "School of Education",
        "School of Social Sciences",
        "School of the Arts & Media",
        "Social Research in Health",
    ],
    "Business School": [
        "AGSM MBA Programs",
        "School of Acctng, Audit & Tax",
        "School of Banking & Finance",
        "School of Economics",
        "School of Management & Gov'nce",
        "School of Marketing",
        "School of Risk & Actuarial St",
        "Sch Info Sys and Tech Mgmt",
        "UNSW Business School",
    ],
    "Engineering": [
        "Faculty of Engineering",
        "Grad. School of Biomedical Eng",
        "Grad. School of Engineering",
        "Minerals Energy Resources Eng",
        "Photovoltaic Engineering",
        "School of Chemical Engineering",
        "School of Civil & Env Eng",
        "School of Computer Sci & Eng",
        "School of Elec Eng & Telco",
        "School of Materials Sci & Eng",
        "School of Mech & Manf. Eng",
        "School of Mining Engineering",
        "School of Petroleum Eng",
    ],
    "Law & Justice": [
        "Faculty of Law and Justice",
    ],
    "Medicine & Health": [
        "Faculty of Medicine and Health",
        "Schl of Optometry & Vision Sci",
        "School of Biomedical Sciences",
        "School of Clinical Medicine",
        "School of Health Sciences",
        "School of Population Health",
    ],
    "Science": [
        "Faculty of Science",
        "Sch Biol, Earth & Environ Sci",
        "Sch Biotech & Biomolecular Sci",
        "Sch Mathematics & Statistics",
        "School of Aviation",
        "School of Chemistry",
        "School of Physics",
        "School of Psychology",
    ],
    "Other / Unclassified": [
        "Canberra Sch of Prof Studies",
        "Div. Registrar & Deputy Princ",
        "Nura Gili Indigenous Programs",
        "Std Acad & Career Success",
        "Student Administration Dept",
        "UC Humanities and Soc Science",
        "UC School of Business",
        "UC Science",
        "UNSW Canberra at ADFA",
        "UNSW College Diplomas",
    ],
}


def clean_text(text):
    text = text.replace("Â", "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def validate_course_code(course_code):
    code = course_code.strip().upper()
    if not re.fullmatch(COURSE_CODE_PATTERN, code):
        raise ValueError("Invalid format for course code.")
    return code


def validate_subject_code(subject_code):
    code = subject_code.strip().upper()
    if not re.fullmatch(SUBJECT_CODE_PATTERN, code):
        raise ValueError("Invalid format for subject code.")
    return code


def classify_faculty(offered_by):
    offered_by_lower = offered_by.lower()
    for faculty, keywords in FACULTIES.items():
        for keyword in keywords:
            if keyword.lower() in offered_by_lower:
                return faculty
    return "Other / Unclassified"


def get_course_level(course_code):
    match = re.fullmatch(r"[A-Z]{4}(\d)\d{3}", course_code.strip().upper())
    if not match:
        return "Other"
    return f"Level {match.group(1)}"


def get_handbook_level(course_code):
    code = validate_course_code(course_code)
    first_digit = int(code[4])
    return "Undergraduate" if first_digit < 5 else "Postgraduate"


def format_section_lines(lines):
    formatted_lines = []
    in_list = False

    for index, line in enumerate(lines):
        previous_line = lines[index - 1] if index > 0 else ""
        if previous_line.endswith(":"):
            in_list = True

        formatted_lines.append(f"- {line}" if in_list else line)

    return formatted_lines
