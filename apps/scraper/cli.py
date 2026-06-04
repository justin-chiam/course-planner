import argparse
import json
from pathlib import Path
import sys
import textwrap

from .normalise import validate_course_code, validate_subject_code
from .scraper import (
    YEAR,
    course_details_to_dict,
    course_to_dict,
    extract_subject_courses,
    extract_timetable_details,
)


def write_json(data, output_path=None):
    text = json.dumps(data, indent=2)

    if output_path:
        output_path = Path(output_path).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(text)
            file.write("\n")
    else:
        print(text)


def print_wrapped_section(text, width):
    paragraphs = text.split("\n")

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            print()
        elif paragraph.startswith("- "):
            print(textwrap.fill(paragraph, width=width, subsequent_indent=" "))
        else:
            print(textwrap.fill(paragraph, width=width))
            print()


def print_course_details(course):
    print("\n" + "=" * 83)
    print(f"{course['code']} - {course['title']}")
    print(f"Timetable URL: {course['timetableUrl']}")
    print(f"Handbook URL:  {course['handbookUrl']}")
    print("=" * 83)

    print("\nOVERVIEW")
    print("-" * 83)
    print_wrapped_section(course["description"], 83)

    print("\nCONDITIONS FOR ENROLMENT")
    print("-" * 83)
    print_wrapped_section(course["enrolmentConditions"], 83)


def scrape_course(args):
    course_code = validate_course_code(args.course_code)
    course = course_details_to_dict(course_code, args.year)

    if args.json or args.output:
        write_json(course, args.output)
    else:
        print_course_details(course)


def scrape_subject(args):
    subject_code = validate_subject_code(args.subject_code)
    courses = extract_subject_courses(subject_code, args.level, args.year)

    for course in courses:
        timetable_details = extract_timetable_details(course.code, args.year)
        course.terms = timetable_details["terms"]
        if course.faculty is None:
            course.faculty = timetable_details["faculty"]
        if course.school is None:
            course.school = timetable_details["school"]

    course_data = [course_to_dict(course) for course in courses]

    if args.details:
        detailed_courses = []
        for course, data in zip(courses, course_data):
            detailed_courses.append(
                course_details_to_dict(
                    course.code,
                    args.year,
                    data["timetableUrl"],
                    course.uoc,
                    course.faculty,
                    course.school,
                    course.terms,
                    course.title,
                )
            )
        course_data = detailed_courses

    if args.json or args.output:
        write_json(course_data, args.output)
    else:
        for course in course_data:
            print(
                f"{course['code']} - {course['title']} "
                f"({course.get('uoc', '?')} UOC)"
            )


def export_courses(args):
    subject_code = validate_subject_code(args.subject_code)
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    for level in args.levels:
        courses = extract_subject_courses(subject_code, level, args.year)

        for course in courses:
            timetable_details = extract_timetable_details(course.code, args.year)
            course.terms = timetable_details["terms"]
            if course.faculty is None:
                course.faculty = timetable_details["faculty"]
            if course.school is None:
                course.school = timetable_details["school"]

        course_data = []
        for course in courses:
            course_data.append(
                course_details_to_dict(
                    course.code,
                    args.year,
                    course.url,
                    course.uoc,
                    course.faculty,
                    course.school,
                    course.terms,
                    course.title,
                )
            )

        filename = f"{subject_code.lower()}-{level.lower()}-courses.json"
        output_path = output_dir / filename
        write_json(course_data, output_path)
        print(f"Wrote {len(course_data)} {level} courses to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape UNSW course data for the course planner."
    )
    subparsers = parser.add_subparsers(dest="command")

    course_parser = subparsers.add_parser(
        "scrape-course", help="scrape one course from the Handbook"
    )
    course_parser.add_argument("course_code", help="course code, e.g. COMP2521")
    course_parser.add_argument(
        "-y",
        "--year",
        type=int,
        default=YEAR,
        help=f"Handbook year, default: {YEAR}",
    )
    course_parser.add_argument("--json", action="store_true", help="print JSON")
    course_parser.add_argument("-o", "--output", help="write JSON to this file")
    course_parser.set_defaults(func=scrape_course)

    subject_parser = subparsers.add_parser(
        "scrape-subject", help="scrape all courses in a subject area"
    )
    subject_parser.add_argument("subject_code", help="subject code, e.g. COMP")
    subject_parser.add_argument(
        "--level",
        choices=["Undergraduate", "Postgraduate", "Research"],
        default="Undergraduate",
        help="timetable section to scrape",
    )
    subject_parser.add_argument(
        "-y", "--year", type=int, default=YEAR, help=f"timetable year, default: {YEAR}"
    )
    subject_parser.add_argument(
        "--details",
        action="store_true",
        help="also scrape each course Handbook page",
    )
    subject_parser.add_argument("--json", action="store_true", help="print JSON")
    subject_parser.add_argument("-o", "--output", help="write JSON to this file")
    subject_parser.set_defaults(func=scrape_subject)

    export_parser = subparsers.add_parser(
        "export-courses",
        help="export subject courses into separate JSON files by level",
    )
    export_parser.add_argument("subject_code", help="subject code, e.g. COMP")
    export_parser.add_argument(
        "-y", "--year", type=int, default=YEAR, help=f"timetable year, default: {YEAR}"
    )
    export_parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="directory to write JSON files into",
    )
    export_parser.add_argument(
        "--levels",
        nargs="+",
        choices=["Undergraduate", "Postgraduate", "Research"],
        default=["Undergraduate", "Postgraduate", "Research"],
        help="course levels to export separately",
    )
    export_parser.set_defaults(func=export_courses)

    parser.add_argument(
        "-c",
        "--course",
        help="scrape a specific course, e.g. -c COMP2521",
    )
    parser.add_argument(
        "-s",
        "--subject",
        help="scrape a subject area, e.g. -s COMP",
    )
    parser.add_argument(
        "-y", "--year", type=int, default=YEAR, help="year for commands"
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("-o", "--output", help="write to JSON file")

    return parser.parse_args()


def main():
    args = parse_args()

    try:
        if args.command:
            args.func(args)
        elif args.course:
            args.course_code = args.course
            scrape_course(args)
        elif args.subject:
            args.subject_code = args.subject
            args.level = "Undergraduate"
            args.details = False
            scrape_subject(args)
        else:
            print("Choose scrape-course or scrape-subject. Use --help for examples.")
            sys.exit(1)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
