import anthropic

SYSTEM_PROMPT = """You are a note-taking assistant for college students.
Given a lecture transcript, produce clean, structured study notes in Markdown.

Format your notes as:
# [Course] — [Inferred Topic]

## Key Concepts
- Bullet each major idea with a 1-2 sentence explanation

## Definitions
- **Term**: definition (only include if explicitly defined)

## Important Details & Examples
- Numbered list of supporting facts, formulas, or examples the professor emphasized

## Questions to Review
- 3-5 questions a student should be able to answer after this lecture

Keep notes concise — dense, scannable bullets over full sentences.
If the transcript is unclear or incomplete, do your best and note gaps."""


CASUAL_PROMPT = """You are summarizing a casual conversation or informal recording for the person who was in it.
Write a detailed, natural summary — like you're catching up a friend who wasn't there.
Cover all the main topics, what was said, and any interesting details. Keep it conversational, not academic.
Use bold headers for the main topic chunks. No bullet lists, just flowing paragraphs."""


def generate_casual_summary(transcript: str, context: str = "") -> str:
    """Generate a conversational summary of any recording (not just lectures)."""
    client = anthropic.Anthropic()

    user_message = f"{('Context: ' + context + chr(10) + chr(10)) if context else ''}Transcript:\n{transcript}"

    print("Generating summary with Claude...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=CASUAL_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def generate_notes(transcript: str, course: str) -> str:
    """Call Claude to turn a transcript into structured notes."""
    client = anthropic.Anthropic()

    user_message = f"Course: {course}\n\nTranscript:\n{transcript}"

    print("Generating notes with Claude...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
