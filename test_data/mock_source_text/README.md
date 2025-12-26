# Mock Source Text (Pass B)

If **Pass B** (summarization) is enabled but **Pass A** (long-form generation) is disabled for a topic,
the pipeline needs an input text to summarize.

Place a plain-text file here:

- `test_data/mock_source_text/<topic-id>.txt`

Example:
- `test_data/mock_source_text/topic-01.txt`

The generator will read this file and use it as `SOURCE_TEXT` for Pass B.
Before sending to OpenAI, the text is escaped via `stringify_for_prompt()` to
reduce the chance that special characters break JSON parsing or prompt formatting.
