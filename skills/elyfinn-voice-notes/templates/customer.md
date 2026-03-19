You are my business assistant. Generate a communication record from the customer call transcript below.

**Output language**: Same as the transcript (Chinese transcript → Chinese output, English → English)

Requirements:
1) Output must be Markdown.
2) Title format: # {date_str} {type_prefix}-<customer/company name>
3) Structure:
   - ## Participants (their side, our side)
   - ## 📋 Their Requirements
   - ## ✅ Our Commitments (use - [ ] checkboxes, note deadlines)
   - ## 💰 Business Info (pricing, budget, timeline if mentioned)
   - ## 📝 Key Information
   - ## ➡️ Next Steps
4) Focus on **commitment tracking** — do not miss any promises we made.

[Transcript]
{transcript}
