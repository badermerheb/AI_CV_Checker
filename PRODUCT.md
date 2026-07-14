# CV Checker

A recruiter tool: upload candidate CVs, then chat with them. Answers are grounded in
the actual CV text and carry numbered citations that open the exact source passage.

## Audience

Recruiters and hiring managers screening a stack of CVs between calls. They are in a
task, not browsing: calm focus, quick scanning, zero friction.

## Register

product — design serves the task. Earned familiarity over surprise.

## Platform

web

## Views

- **Chat** — the core surface. Ask anything; answers cite sources; citation chips
  highlight the matching source card. Empty state teaches with example questions.
- **Candidates** — dense table of extracted profiles (name, title, experience,
  location) with expandable detail (skills, education, languages, certifications).
- **Upload CVs** — drag-and-drop PDF/DOCX, sequential ingestion with per-file status.
  Re-uploading a file replaces its earlier version.

## Design system (tokens live in frontend/src/index.css)

- Mood: herbarium archive — bottle-green ink on white paper, precise labels.
- Color strategy: restrained. Pure white bg, green-tinted panel neutral for the
  sidebar, one bottle-green primary (oklch 0.42 0.09 160) for actions/selection/state.
- Type: Instrument Sans for all UI; JetBrains Mono reserved for reference material
  (citation chips, source labels, table headers, filenames) — the signature element.
- Motion: 150–200ms ease-out state transitions only; reduced-motion respected.
