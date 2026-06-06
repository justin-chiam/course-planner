import "dotenv/config";

import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import fs from "node:fs/promises";
import path from "node:path";

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is required to seed the database.");
}

const adapter = new PrismaPg({
  connectionString: process.env.DATABASE_URL,
});

const prisma = new PrismaClient({
  adapter,
});

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

const OFFERING_BATCH_SIZE = 100;
const COURSE_UPSERT_BATCH_SIZE = 10;

function chunks<T>(items: T[], size: number) {
  const result: T[][] = [];

  for (let index = 0; index < items.length; index += size) {
    result.push(items.slice(index, index + size));
  }

  return result;
}

function toCourseData(course: ScrapedCourse) {
  return {
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
  };
}

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

  console.log(`Read ${courses.length} courses`);

  for (const batch of chunks(courses, COURSE_UPSERT_BATCH_SIZE)) {
    await Promise.all(
      batch.map((course) => {
        const data = toCourseData(course);

        return prisma.course.upsert({
          where: {
            code: course.code,
          },
          create: data,
          update: data,
        });
      }),
    );
  }

  console.log("Upserted courses");

  const savedCourses = await prisma.course.findMany({
    where: {
      code: {
        in: courses.map((course) => course.code),
      },
    },
    select: {
      id: true,
      code: true,
    },
  });
  const courseIdsByCode = new Map(
    savedCourses.map((course) => [course.code, course.id]),
  );
  const courseIds = savedCourses.map((course) => course.id);
  const years = Array.from(new Set(courses.map((course) => course.year)));

  const offerings = courses.flatMap((course) => {
    const courseId = courseIdsByCode.get(course.code);

    if (!courseId) {
      throw new Error(`Course ${course.code} was not saved.`);
    }

    return (course.terms ?? []).map((term) => ({
      courseId,
      year: course.year,
      term,
    }));
  });

  await prisma.$transaction(async (tx) => {
    await tx.courseOffering.deleteMany({
      where: {
        courseId: {
          in: courseIds,
        },
        year: {
          in: years,
        },
      },
    });

    for (const batch of chunks(offerings, OFFERING_BATCH_SIZE)) {
      await tx.courseOffering.createMany({
        data: batch,
      });
    }
  });

  console.log("Refreshed offerings");

  console.log(`Seeded ${courses.length} courses and ${offerings.length} offerings`);
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
