# Thirty Lessons TDD

## Summary

Thirty Lessons is a self-hosted, open-source learning platform for "30 Days to Learn Anything." It helps a user create and complete 30-day learning programs on arbitrary topics. The user defines a topic through a guided chat interface, the system generates a rough 30-day outline, and then a daily job generates and emails one lesson per day. Each lesson is stored in the application for later review, and the user can provide feedback through quick actions or freeform comments that influence future lesson generation.

The application will be built with Django, HTMX, PostgreSQL, Docker Compose, and Playwright integration tests. The first version is designed for single-user/self-hosted use, not multi-tenant SaaS.

## Core Goals

The system should allow a user to:

1. Create one or more learning topics.
2. Refine a topic through a chat-style interface.
3. Generate a 30-day course outline.
4. Activate, pause, complete, or archive a course.
5. Generate daily lessons from the course context.
6. Send each lesson by email.
7. View all lessons in the web interface.
8. Leave quick-action feedback and freeform comments.
9. Use prior lessons, comments, and stable course context to improve future lesson generation.

## Non-Goals for MVP

The MVP will not include billing, multi-user teams, public sharing, mobile apps, complex analytics, gamification, or a full LMS feature set. The app should stay focused on personal course generation, daily lesson delivery, feedback, and review.

## Tech Stack

Backend:

* Django
* Django templates
* HTMX
* PostgreSQL
* Celery or Django management command for scheduled generation
* SMTP/email backend
* AI provider adapter abstraction

Frontend:

* Django templates
* HTMX for partial updates
* Minimal JavaScript
* Server-rendered pages

Testing:

* Django unit tests
* Django integration tests
* Playwright browser tests

Infrastructure:

* Dockerfile for app image
* docker-compose.yml for local/self-hosted runtime
* Postgres service
* Optional worker service
* Optional scheduler service

## Docker Requirements

The project must support:

```bash
docker compose build
docker compose up
docker compose down
```

Recommended services:

```yaml
services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: learning
      POSTGRES_USER: learning
      POSTGRES_PASSWORD: learning

  worker:
    build: .
    command: python manage.py run_daily_lessons

  scheduler:
    build: .
    command: python manage.py scheduler
```

For MVP, the scheduler can be simple. A cron job or scheduled container can call a Django management command once per day. The important part is that lesson generation is not tied to a web request.

Acceptance criteria:

* `docker compose build` builds the app image successfully.
* `docker compose up` starts Django and Postgres.
* Visiting the app in a browser loads the homepage.
* `docker compose down` stops all services cleanly.
* The app can run database migrations inside Docker.
* The daily lesson generation command can run inside Docker.

## Data Model

### Topic

Represents the broad subject the user wants to learn.

Fields:

* id
* title
* description
* created_at
* updated_at

Example topics:

* Piano history
* Thought-provoking philosophy of the Stoics
* Beginner electrical theory
* Rust systems programming

### Course

Represents a 30-day learning program generated from a topic.

Fields:

* id
* topic_id
* title
* goal
* audience_level
* lesson_style
* daily_time_commitment
* status
* stable_context
* outline
* created_at
* updated_at
* started_at
* completed_at

Statuses:

* draft
* active
* paused
* completed
* archived

### ChatMessage

Stores the guided conversation used to define the course.

Fields:

* id
* course_id
* role
* content
* created_at

Roles:

* user
* assistant
* system

### Lesson

Represents a generated daily lesson.

Fields:

* id
* course_id
* day_number
* title
* content_markdown
* summary
* email_sent_at
* generated_at
* created_at
* updated_at

### LessonFeedback

Stores quick actions and comments on lessons.

Fields:

* id
* lesson_id
* feedback_type
* comment
* created_at

Feedback types:

* too_easy
* too_hard
* good_pacing
* more_practical
* more_theory
* more_examples
* confusing
* skip_ahead
* custom_comment

### CourseMemory

Stores compressed long-term context for the course.

Fields:

* id
* course_id
* content
* created_at
* updated_at

This is used to avoid sending every historical message and lesson to the AI forever.

## AI Context Strategy

Each daily lesson generation request should include layered context instead of blindly sending the entire history.

The request should include:

1. Stable course context:

   * topic
   * course goal
   * skill level
   * desired tone
   * preferred lesson length
   * daily time commitment

2. 30-day outline:

   * full outline
   * current day number
   * current day outline item

3. Recent lesson context:

   * previous 1 to 3 lesson summaries
   * previous lesson titles
   * relevant exercises or unresolved concepts

4. User feedback:

   * quick-action feedback from recent lessons
   * comments from recent lessons
   * recurring feedback themes

5. Course memory:

   * compressed summary of what the user prefers
   * repeated struggles
   * areas needing reinforcement
   * pacing notes

The system should save the generated lesson, create a summary, and optionally update course memory after each lesson.

Acceptance criteria:

* Daily lesson generation includes stable course context.
* Daily lesson generation includes the current outline item.
* Daily lesson generation includes recent lesson summaries when available.
* Daily lesson generation includes feedback from previous lessons.
* The app does not require sending the entire course history forever.
* Generated lessons are saved before email is sent.
* Failed email delivery does not delete or lose the generated lesson.

## User Stories and Acceptance Criteria

### 1. Create Topic

As a user, I want to create a new learning topic so that I can start building a 30-day course.

Acceptance criteria:

* User can enter a topic title.
* User can optionally enter a topic description.
* After saving, the topic appears in the topic list.
* Empty title is rejected.
* Duplicate titles are allowed for MVP.

Playwright test:

* Visit topic list.
* Click “New Topic.”
* Enter “Piano History.”
* Submit form.
* Verify “Piano History” appears in the topic list.

### 2. Create Course From Topic

As a user, I want to create a 30-day course from a topic so that I can define a structured learning path.

Acceptance criteria:

* User can create a course from a topic page.
* New course starts in `draft` status.
* User can define goal, level, lesson style, and daily time commitment.
* Course is associated with the topic.

Playwright test:

* Create topic.
* Click “Create Course.”
* Fill course goal and preferences.
* Submit.
* Verify draft course page loads.

### 3. Guided Chat Interface

As a user, I want to refine my course through a chat interface so that the AI can help me shape the course before generating the outline.

Acceptance criteria:

* User can submit chat messages.
* Assistant response is displayed on the page.
* Chat messages are persisted.
* HTMX updates the chat panel without full page reload.
* User can continue the conversation later.

Playwright test:

* Open draft course.
* Enter chat message: “I want this focused on composers and piano evolution.”
* Submit.
* Verify user message appears.
* Verify assistant response appears.
* Reload page.
* Verify messages are still present.

### 4. Generate 30-Day Outline

As a user, I want to generate a rough 30-day outline so that the course has structure before daily lessons begin.

Acceptance criteria:

* User can click “Generate Outline.”
* System calls AI with topic, course settings, and chat history.
* Outline contains 30 day entries.
* Outline is saved to the course.
* User can view the outline before activating.
* Course remains in draft status after outline generation.

Playwright test:

* Open draft course with chat messages.
* Click “Generate Outline.”
* Verify 30 outline items render.
* Verify course status remains draft.

### 5. Activate Course

As a user, I want to activate a course so that daily lessons begin.

Acceptance criteria:

* Course can only be activated if it has a valid 30-day outline.
* Activated course status becomes `active`.
* started_at is set.
* Active course appears in active courses list.
* Draft courses without outline cannot be activated.

Playwright test:

* Generate outline.
* Click “Activate Course.”
* Verify status is active.
* Verify course appears under active courses.

### 6. Pause Course

As a user, I want to pause a course so that daily lesson generation temporarily stops.

Acceptance criteria:

* Active course can be paused.
* Paused course status becomes `paused`.
* Daily lesson generation skips paused courses.

Playwright test:

* Activate course.
* Click “Pause.”
* Verify status is paused.

Backend integration test:

* Create paused course.
* Run daily lesson command.
* Verify no lesson is generated.

### 7. Generate Daily Lesson

As a user, I want the system to generate the correct daily lesson so that I receive one lesson per course day.

Acceptance criteria:

* Daily command finds active courses.
* System determines the next missing day number.
* System generates only one lesson per course per run.
* Lesson is saved to database.
* Lesson includes title, content, day number, and summary.
* Existing lesson for the day is not duplicated.

Backend integration test:

* Create active course with outline.
* Run daily lesson command.
* Verify lesson day 1 exists.
* Run command again same day.
* Verify no duplicate lesson is created.

### 8. Send Daily Lesson Email

As a user, I want each lesson emailed to me so that learning arrives without me opening the app.

Acceptance criteria:

* Generated lesson is sent by email.
* Email includes lesson title, content excerpt or full content, and links.
* Email includes quick-action feedback links.
* Email includes “View lesson” link.
* email_sent_at is set after successful send.
* Failed email send is logged and can be retried.

Playwright test:

* Not ideal for email delivery itself.
* Use backend test with Django test email backend.

Backend integration test:

* Generate lesson.
* Verify one email was sent.
* Verify email contains “View lesson.”
* Verify email contains feedback links.

### 9. View Lesson

As a user, I want to view a lesson in the web app so that I can review and reflect on it.

Acceptance criteria:

* Lesson page displays title, day number, content, and course.
* Markdown content is rendered safely.
* Feedback form appears below lesson.
* Existing feedback/comments are visible.

Playwright test:

* Create lesson fixture.
* Visit lesson page.
* Verify title and content appear.
* Verify feedback controls are visible.

### 10. Quick Action Feedback

As a user, I want to click quick feedback actions from email or the web page so that I can easily guide future lessons.

Acceptance criteria:

* Quick-action links create LessonFeedback records.
* User can click feedback link without needing to fill a full form.
* Duplicate quick-action clicks are either allowed or idempotently handled.
* Feedback appears on the lesson page.

Playwright test:

* Open lesson page.
* Click “More Practical.”
* Verify feedback appears.
* Verify page updates through HTMX or redirects cleanly.

### 11. Freeform Lesson Comments

As a user, I want to leave comments on a lesson so that future lessons can adapt to my thoughts, confusion, or interests.

Acceptance criteria:

* User can submit a comment on a lesson.
* Comment is saved.
* Comment appears on the lesson page.
* Empty comments are rejected.
* Comments are included in future AI context.

Playwright test:

* Open lesson page.
* Enter comment: “This was too abstract. I need more examples.”
* Submit.
* Verify comment appears after save.
* Reload page.
* Verify comment persists.

### 12. Course Memory Update

As a user, I want the system to remember recurring preferences so that each lesson gets better without resending all history forever.

Acceptance criteria:

* System can generate or update CourseMemory.
* CourseMemory includes useful compressed context.
* Daily lesson generation includes CourseMemory.
* CourseMemory can be viewed in admin or debug page.

Backend integration test:

* Create course with lessons and feedback.
* Run memory update command.
* Verify CourseMemory exists.
* Verify future lesson prompt includes CourseMemory.

### 13. Archive Course

As a user, I want to archive a course so that it is hidden from my active workspace but not deleted.

Acceptance criteria:

* Course status can be changed to archived.
* Archived courses do not receive daily lessons.
* Archived courses remain viewable from archive page.
* Lessons and feedback are preserved.

Playwright test:

* Open course.
* Click “Archive.”
* Verify course no longer appears in active list.
* Open archive page.
* Verify course appears.

## Playwright Test Coverage

Playwright should focus on workflows that matter from the user’s perspective:

1. Topic creation.
2. Course creation.
3. Chat interaction.
4. Outline generation.
5. Course activation.
6. Course pause/archive.
7. Lesson viewing.
8. Quick feedback.
9. Freeform comments.
10. HTMX updates.

AI calls should be mocked or replaced with deterministic test responses.

Email sending should be tested mostly in Django backend tests, not browser tests.

## AI Provider Abstraction

The app should not hard-code one AI provider throughout the application.

Recommended interface:

```python
class AIProvider:
    def generate_chat_response(self, messages: list[dict]) -> str:
        ...

    def generate_course_outline(self, context: dict) -> dict:
        ...

    def generate_daily_lesson(self, context: dict) -> dict:
        ...

    def update_course_memory(self, context: dict) -> str:
        ...
```

Acceptance criteria:

* App code calls an internal AIProvider abstraction.
* Tests can use a fake AI provider.
* Provider errors are handled gracefully.
* Failed generation does not corrupt course state.

## HTMX Requirements

HTMX should be used for small interaction loops:

* chat message submission
* outline generation status/result
* quick feedback
* comment submission
* status changes such as pause/resume/archive

Acceptance criteria:

* HTMX actions return partial templates.
* Full page fallback still works where reasonable.
* Browser tests verify the rendered result, not HTMX internals.

## Management Commands

Required commands:

```bash
python manage.py generate_daily_lessons
python manage.py update_course_memory
python manage.py send_unsent_lessons
```

Optional commands:

```bash
python manage.py generate_course_outline <course_id>
python manage.py seed_demo_data
```

Acceptance criteria:

* Commands can run inside Docker.
* Commands are idempotent where needed.
* Commands log useful output.
* Commands return non-zero on unrecoverable failure.

## MVP Definition of Done

The MVP is complete when:

1. The app runs with Docker Compose.
2. A user can create a topic.
3. A user can create and refine a course.
4. A 30-day outline can be generated and saved.
5. A course can be activated, paused, completed, or archived.
6. Daily lesson generation works from a management command.
7. Lessons are emailed and saved.
8. Lessons can be viewed in the web UI.
9. Quick feedback and comments can be submitted.
10. Future lesson generation includes course context, recent lessons, and feedback.
11. Playwright tests cover the main user workflows.
12. Django tests cover model behavior, management commands, email sending, and AI provider integration.
