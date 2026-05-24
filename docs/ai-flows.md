# AI Flows

Thirty Lessons uses AI as a course-design and lesson-generation assistant. The app does not treat AI as the source of truth for application state. Django owns the workflow, validates AI output, stores durable records, and decides when each AI call happens.

## Design Goals

- Keep AI access behind a provider boundary so the app can run with OpenAI or a deterministic fake provider.
- Use bounded context instead of sending the full course history forever.
- Separate planning, outline generation, lesson generation, and memory compression into distinct calls.
- Save generated lessons before email delivery so failed email does not lose work.
- Let feedback influence future lessons without rewriting past lessons automatically.

## Provider Boundary

AI access lives in `src/courses/ai.py`.

The app uses `get_ai_provider()` to choose a provider:

- `FakeAIProvider` is used when no OpenAI key is configured or when `AI_PROVIDER=fake`.
- `OpenAIProvider` is used when `AI_PROVIDER=openai` or an `OPENAI_KEY` is present.

The rest of the app talks to the provider interface rather than the OpenAI client directly. This keeps tests deterministic and limits provider-specific code to one module.

The provider interface currently supports:

- `generate_initial_course_message(context)`
- `generate_chat_response(messages)`
- `generate_course_outline(context)`
- `generate_daily_lesson(context)`
- `update_course_memory(context)`

## Course Creation and Initial Chat

When a course is created, the app stores the user-provided course settings:

- title
- goal
- audience level
- lesson style
- daily time commitment
- stable context

After saving the course, the app asks AI to start a refinement conversation. The goal of this first message is not to create the outline. It should ask targeted planning questions that help clarify what the learner wants before a 30-day structure is generated.

The initial AI context includes:

- topic title and description
- course title
- course goal
- audience level
- lesson style
- daily time commitment
- stable context

The assistant response is saved as a `ChatMessage` with role `assistant`.

## Refinement Chat

When the learner sends a chat message, the app:

1. Saves the user message as a `ChatMessage`.
2. Builds a system/developer context from the topic and course settings.
3. Appends the saved chat history.
4. Sends the conversation to the provider.
5. Saves the assistant response as another `ChatMessage`.

The chat prompt asks AI to behave like a course-design partner. It should reflect user preferences, ask useful follow-up questions, and avoid generating the full 30-day outline inside chat.

This keeps the chat phase exploratory while preserving a clean transition to structured outline generation.

## Outline Generation

When the learner clicks "Generate Outline", the app calls `generate_outline(course)`.

The outline request includes:

- topic context
- course settings
- stable context
- chat history

The provider must return exactly 30 outline items. Each item must include:

- `day`
- `title`
- `objective`

The app validates the response before saving it:

- the outline must be a list
- the list must contain exactly 30 items
- each item must be a dictionary/object
- each `day` must match its 1-based position
- each `title` must be a non-empty string
- each `objective` must be a non-empty string

The course remains in `draft` status after outline generation. A course can only be activated after it has a valid 30-day outline.

## Daily Lesson Generation

Daily lesson generation is command-driven, not web-request-driven.

The core command is:

```bash
python manage.py generate_daily_lessons
```

For each active course, the app:

1. Skips the course if it is not active.
2. Skips the course if a lesson has already been generated today.
3. Finds the first missing day from 1 through 30.
4. Marks the course completed if all 30 lessons already exist.
5. Builds bounded lesson context.
6. Requests one daily lesson from AI.
7. Validates the lesson response.
8. Saves the lesson.
9. Sends the email unless email delivery was disabled for the command.

The lesson context includes:

- topic title and description
- course title, goal, level, style, daily time commitment, and stable context
- full 30-day outline
- current day number
- current day outline item
- up to 3 previous lesson summaries
- up to 10 recent feedback items
- current course memory, if one exists

The provider must return:

- `title`
- `content_markdown`
- `summary`

The app rejects malformed or empty values before saving.

## Email Delivery

Generated lessons are saved before email is sent. If email delivery fails, the lesson remains in the database with `email_sent_at` unset so it can be retried later.

Emails are sent as multipart messages:

- plain-text fallback
- HTML alternative

The HTML alternative renders lesson Markdown through the same sanitized Markdown renderer used by the web UI. Quick feedback links are real HTML anchors.

Email feedback links open the lesson page with a confirmation modal:

```text
/lessons/<lesson_id>/?feedback=<feedback_type>#feedback-modal
```

Opening the link does not save feedback. Feedback is only saved by submitting the confirmation form with `POST`.

## Feedback Flow

Feedback is stored as `LessonFeedback`.

There are two feedback paths:

- quick feedback, such as `too_hard`, `more_examples`, or `more_practical`
- freeform comments

Quick feedback from the lesson page or email opens a confirmation modal. The learner can optionally add a comment before saving.

Feedback does not immediately call AI and does not rewrite the current lesson. Instead, recent feedback is included in future daily lesson context.

This keeps feedback simple and predictable:

```text
Generate lesson -> learner gives feedback -> future lesson sees feedback
```

## Course Memory

Course memory is a compressed long-term summary stored in `CourseMemory`.

The memory command is:

```bash
python manage.py update_course_memory
```

It sends the provider:

- course context
- lesson summaries
- feedback
- current memory, if one exists

The provider returns a short memory string that captures durable guidance for future generation, such as recurring preferences, pacing notes, repeated confusion, or desired lesson style.

Course memory exists because recent feedback is intentionally bounded. Daily generation only includes a small number of recent feedback items, while memory preserves longer-running patterns without sending every historical lesson and feedback record forever.

## Cron Flow

The host cron job should call:

```bash
/home/buddy/Documents/Programming/30day-newsletter/scripts/send_email.sh
```

That script currently:

1. Resolves the project root.
2. Loads `.env` and `.env.email` when present.
3. Runs `update_course_memory`.
4. Runs `generate_daily_lessons`.

This means the daily lesson generated at 8 AM can use feedback and memory from prior lessons.

## Failure Behavior

AI provider errors are converted into `GenerationError` in the service layer.

Outline generation failure does not activate or corrupt the course.

Lesson generation failure does not create a partial lesson.

Email failure does not delete the generated lesson. The lesson can be retried with:

```bash
python manage.py send_unsent_lessons
```

## Current Tradeoffs

- Feedback affects future lessons, not the current lesson.
- Course memory updates through the cron script, not immediately after every feedback event.
- Daily generation sends the full outline, but only bounded recent lesson and feedback history.
- The app is optimized for one self-hosted learner, not multi-user SaaS isolation.
- The fake provider is intentionally simple and deterministic for local use and tests.
