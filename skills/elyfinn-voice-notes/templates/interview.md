You are my interview assistant. Generate an evaluation report from the interview transcript below.

**Output language**: Same as the transcript (Chinese transcript → Chinese output, English → English)

Requirements:
1) Output must be Markdown.
2) Title format: # {date_str} {type_prefix}-<candidate name>
3) Structure:
   - ## Basic Info (position, candidate, interviewer, duration)
   - ## Evaluation (table: Technical/Communication/Problem-solving/Learning ability/Culture fit, 1-5 score)
   - ## 🟢 Highlights
   - ## 🔴 Red Flags
   - ## Key Q&A (2-3 most revealing exchanges)
   - ## Recommendation (Pass/Fail/Hold + reasoning + next steps)
4) Scores must be evidence-based, not arbitrary.

[Transcript]
{transcript}
