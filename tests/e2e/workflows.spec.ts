import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';

function manage(command: string) {
  if (process.env.E2E_DOCKER === '1') {
    execFileSync('docker', ['compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c', command], {
      env: process.env,
      stdio: 'inherit',
    });
    return;
  }
  execFileSync('.venv312/bin/python', ['manage.py', 'shell', '-c', command], {
    env: process.env,
    stdio: 'inherit',
  });
}

test.beforeEach(() => {
  manage(`
from courses.models import Topic, Course, ChatMessage, Lesson, LessonFeedback, CourseMemory
LessonFeedback.objects.all().delete()
Lesson.objects.all().delete()
ChatMessage.objects.all().delete()
CourseMemory.objects.all().delete()
Course.objects.all().delete()
Topic.objects.all().delete()
`);
});

test('topic creation and draft course creation', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'New Topic' }).click();
  await page.getByLabel('Title:').fill('Piano History');
  await page.getByLabel('Description:').fill('Composers and instrument evolution.');
  await page.getByRole('button', { name: 'Save Topic' }).click();

  await expect(page.getByRole('heading', { name: 'Piano History' })).toBeVisible();
  await page.getByRole('link', { name: 'Create Course' }).click();
  await page.getByLabel('Goal:').fill('Understand composers and piano evolution.');
  await page.getByLabel('Audience level:').fill('Beginner');
  await page.getByLabel('Lesson style:').fill('Practical');
  await page.getByLabel('Daily time commitment:').fill('20 minutes');
  await page.getByRole('button', { name: 'Create Course' }).click();

  await expect(page.getByTestId('course-status')).toHaveText('draft');
});

test('chat, outline generation, activation, pause, and archive', async ({ page }) => {
  manage(`
from courses.models import Topic, Course
t=Topic.objects.create(title='Piano History')
Course.objects.create(topic=t,title='Piano Program',goal='Learn piano history',audience_level='Beginner',lesson_style='Practical',daily_time_commitment='20 minutes',stable_context='Stable')
`);

  await page.goto('/');
  await page.getByRole('link', { name: 'Piano History' }).click();
  await page.getByRole('link', { name: /Piano Program/ }).click();

  const beforeUrl = page.url();
  await page.getByLabel('Message:').fill('I want this focused on composers and piano evolution.');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page).toHaveURL(beforeUrl);
  await expect(
    page.getByTestId('chat-message')
      .filter({ hasText: 'User' })
      .filter({ hasText: 'I want this focused on composers and piano evolution.' })
  ).toBeVisible();
  await expect(page.getByText('A useful next step')).toBeVisible();
  await page.reload();
  await expect(page.getByTestId('chat-message')).toHaveCount(2);

  await page.getByRole('button', { name: 'Generate Outline' }).click();
  await expect(page.getByTestId('outline-item')).toHaveCount(30);
  await expect(page.getByTestId('course-status')).toHaveText('draft');

  await page.getByRole('button', { name: 'Activate' }).click();
  await expect(page.getByTestId('course-status')).toHaveText('active');
  await page.getByRole('link', { name: 'Active Courses' }).click();
  await expect(page.getByRole('link', { name: 'Piano Program' })).toBeVisible();

  await page.getByRole('link', { name: 'Piano Program' }).click();
  await page.getByRole('button', { name: 'Pause' }).click();
  await expect(page.getByTestId('course-status')).toHaveText('paused');
  await page.getByRole('button', { name: 'Archive' }).click();
  await expect(page.getByTestId('course-status')).toHaveText('archived');
  await page.getByRole('link', { name: 'Archive' }).click();
  await expect(page.getByRole('link', { name: 'Piano Program' })).toBeVisible();
});

test('activation guard without outline', async ({ page }) => {
  manage(`
from courses.models import Topic, Course
t=Topic.objects.create(title='Electrical Theory')
Course.objects.create(topic=t,title='Electrical Program',goal='Learn basics',audience_level='Beginner',lesson_style='Practical',daily_time_commitment='15 minutes')
`);

  await page.goto('/');
  await page.getByRole('link', { name: 'Electrical Theory' }).click();
  await page.getByRole('link', { name: /Electrical Program/ }).click();
  await page.getByRole('button', { name: 'Activate' }).click();

  await expect(page.getByTestId('course-status')).toHaveText('draft');
  await expect(page.getByText('Course needs a 30-day outline')).toBeVisible();
});

test('lesson view, quick feedback, comments, and validation', async ({ page }) => {
  manage(`
from courses.models import Topic, Course, Lesson
t=Topic.objects.create(title='Stoics')
c=Course.objects.create(topic=t,title='Stoic Program',goal='Think clearly',audience_level='Beginner',lesson_style='Reflective',daily_time_commitment='10 minutes')
Lesson.objects.create(course=c,day_number=1,title='Marcus Aurelius',content_markdown='# Marcus Aurelius\\n\\nUseful content.',summary='Summary')
`);

  await page.goto('/');
  await page.getByRole('link', { name: 'Stoics' }).click();
  await page.getByRole('link', { name: /Stoic Program/ }).click();
  await page.getByRole('link', { name: /Day 1: Marcus Aurelius/ }).click();

  await expect(page.getByRole('heading', { name: 'Day 1: Marcus Aurelius' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Marcus Aurelius', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'More practical' }).click();
  await expect(page.getByRole('dialog', { name: 'Confirm Feedback' })).toBeVisible();
  await page.getByLabel('Optional comment:').fill('I need more hands-on examples.');
  await page.getByRole('button', { name: 'Save Feedback' }).click();
  await expect(page.getByTestId('feedback-item')).toContainText('More practical');
  await expect(page.getByText('I need more hands-on examples.')).toBeVisible();
  await page.getByRole('button', { name: 'Save Note' }).click();
  await expect(page.getByText('Comment cannot be empty')).toBeVisible();
  await page.getByLabel('Comment:').fill('This was too abstract. I need more examples.');
  await page.getByRole('button', { name: 'Save Note' }).click();
  await expect(page.getByText('This was too abstract')).toBeVisible();
  await page.reload();
  await expect(page.getByText('This was too abstract')).toBeVisible();
});
