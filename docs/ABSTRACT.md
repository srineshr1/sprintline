# Abstract

**Title:** AI-Enabled Intelligent Project Lifecycle Management System Using Generative AI and Agile Project Management  

**Demo name:** GenAI Agile Copilot  

**Student / owner:** Srinesh R  
**Faculty:** Dr. B. Sandhya  

## Summary

Agile teams spend significant effort turning vague product ideas into structured backlogs, acceptance criteria, sprint plans, and status reports. Existing project trackers excel at recording work but offer little generative assistance; general chatbots produce free-form text without a durable project model or measurable quality controls.

This project implements a **human-in-the-loop, multi-agent lifecycle copilot**: a project brief is transformed into epics and user stories; a **critic agent** flags weak items (missing acceptance criteria, vague titles, oversized estimates, capacity overload); a **sprint agent** proposes capacity-aware scope; a **summarizer** drafts standups from the board; and an **evaluation layer** computes concrete metrics—acceptance-criteria coverage, an INVEST-style rubric score, and planned versus completed/remaining sprint points—for viva and report evidence.

The system is a full-stack monorepo (React + TypeScript + Vite frontend; FastAPI + SQLite backend). Agent logic is structured (JSON + rationale), offline-capable via deterministic stubs that preserve the same API contract as a future LLM backend, and never silently overwrites user-edited stories. The result is not a chatbot wrapper: the **Kanban board and persisted backlog are the source of truth**, while AI agents propose, explain, and score.

## Keywords

Generative AI · Agile · Scrum · Multi-agent systems · Human-in-the-loop · User stories · INVEST · Software project management · Explainable AI
