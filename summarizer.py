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
