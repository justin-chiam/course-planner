import { PrismaClient } from "@prisma/client";
import fs from "node:fs/promises";
import path from "node:path";

const prisma = new PrismaClient();

type ScrapedCourse = {
  code: string;
  title: string;
  subject: string;
  level?: number | null;
  uoc?: number | null;
  faculty?: string | null;
  school?: string | null;
  description?: string | null;
  enrolmentConditions?: string | null;
  handbookUrl?: string | null;
  timetableUrl?: string | null;
  year: number;
  terms?: string[];
};

async function readCourses() {
  const dataDir = path.join(process.cwd(), "../../data/processed/2026");
  const entries = await fs.readdir(dataDir);
  const courseFiles = entries
    .filter((entry) => entry.endsWith("-courses.json"))
    .sort();

  const coursesByCode = new Map<string, ScrapedCourse>();

  for (const file of courseFiles) {
    const filePath = path.join(dataDir, file);
    const raw = await fs.readFile(filePath, "utf-8");
    const courses = JSON.parse(raw) as ScrapedCourse[];

    for (const course of courses) {
      coursesByCode.set(course.code, course);
    }
  }

  return Array.from(coursesByCode.values()).sort((a, b) =>
    a.code.localeCompare(b.code),
  );
}

async function main() {
  const courses = await readCourses();

  for (const course of courses) {
    const savedCourse = await prisma.course.upsert({
      where: {
        code: course.code,
      },
      update: {
        title: course.title,
        subject: course.subject,
        level: course.level ?? null,
        uoc: course.uoc ?? null,
        faculty: course.faculty ?? null,
        school: course.school ?? null,
        description: course.description ?? null,
        enrolmentConditions: course.enrolmentConditions ?? null,
        handbookUrl: course.handbookUrl ?? null,
        timetableUrl: course.timetableUrl ?? null,
        year: course.year,
      },
      create: {
        code: course.code,
        title: course.title,
        subject: course.subject,
        level: course.level ?? null,
        uoc: course.uoc ?? null,
        faculty: course.faculty ?? null,
        school: course.school ?? null,
        description: course.description ?? null,
        enrolmentConditions: course.enrolmentConditions ?? null,
        handbookUrl: course.handbookUrl ?? null,
        timetableUrl: course.timetableUrl ?? null,
        year: course.year,
      },
    });

    const terms = course.terms ?? [];

    await prisma.courseOffering.deleteMany({
      where: {
        courseId: savedCourse.id,
        year: course.year,
        term: {
          notIn: terms,
        },
      },
    });

    for (const term of terms) {
      await prisma.courseOffering.upsert({
        where: {
          courseId_year_term: {
            courseId: savedCourse.id,
            year: course.year,
            term,
          },
        },
        update: {},
        create: {
          courseId: savedCourse.id,
          year: course.year,
          term,
        },
      });
    }
  }

  console.log(`Seeded ${courses.length} courses`);
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error) => {
    console.error(error);
    await prisma.$disconnect();
    process.exit(1);
  });
