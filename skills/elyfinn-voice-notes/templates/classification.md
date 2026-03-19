Analyze the type of this recording transcript.

<transcript>
{transcript_preview}
</transcript>

## Type Definitions

| Type | Characteristics |
|------|-----------------|
| `meeting` | Internal meetings/standups. Multiple participants discussing, decisions & action items |
| `keynote` | Lectures/conferences/podcasts. One or few speakers, structured content, insights & quotes |
| `interview` | Job interviews. Q&A format, interviewer asks, candidate answers |
| `customer` | Sales/BD calls. Business context, requirements, pricing, collaboration |
| `brainstorm` | Brainstorming sessions. Divergent thinking, multiple ideas, no conclusions yet |
| `consult` | Expert consultations. Seeking advice, professional insights |
| `note` | Personal voice memos. Self-talk, recording thoughts or reminders |

## Classification Guidelines

1. Participant count: Single → note/keynote, Multiple → meeting/brainstorm/customer
2. Dialog pattern: One-way → keynote, Q&A → interview, Back-and-forth → meeting
3. Content type: Insights/arguments → keynote, Task assignments → meeting, Business negotiation → customer
4. Context clues: "interview"/"candidate" → interview, "customer"/"pricing" → customer

Output JSON only, no other text:
{{"type": "meeting|keynote|interview|customer|brainstorm|consult|note", "confidence": 0.0-1.0, "reason": "one-line reasoning", "participants": ["identified participants"], "topic": "topic keywords"}}
