# AI Agents Structure

This folder contains all configuration for AI agents (architect, engineer, product, UX) used to analyse the codebase and propose solutions.

## Structure

```
/ai
  /agents        # Role-specific instructions
  /context       # Shared system knowledge
  /playbooks     # Task-specific workflows/prompts
  /schemas       # Structured output definitions
```

---

## 1. /context (shared by all agents)

**Purpose:** Single source of truth about the system.

Contains:

* `architecture_overview.md` → high-level system design
* `product_overview.md` → what the product does
* `tech_stack.md` → frameworks, tools, infra
* `design_principles.md` → rules (e.g. event-driven, API-first)
* `domain_model.md` → key concepts (e.g. intervals, FTP)

👉 Loaded into every agent

---

## 2. /agents (role-specific behaviour)

Each agent has its own folder:

```
/agents/architect/
/agents/engineer/
/agents/product_owner/
/agents/ux/
```

Typical files:

* `system.md` → role, responsibilities, tone
* `constraints.md` → what the agent must avoid
* `<role-specific>.md` → e.g. patterns, coding standards, heuristics

Examples:

* Architect → `patterns.md` (event-driven, trade-offs)
* Engineer → `coding_standards.md`
* UX → `heuristics.md`

👉 Defines *how the agent thinks*

---

## 3. /playbooks (task templates)

**Purpose:** Define repeatable workflows.

Examples:

* `architecture_review.md`
* `feature_design.md`
* `refactor_review.md`

Each playbook:

* describes the task
* guides the agent’s approach
* may define expected sections in output

👉 Defines *what the agent is doing*

---

## 4. /schemas (output structure)

**Purpose:** Enforce consistent, structured responses.

Examples:

* `architecture_review.json`
* `feature_design.json`

Used to:

* standardise outputs
* enable downstream processing
* reduce ambiguity

---

## How it works

At runtime, prompts are composed as:

```
shared context
+ agent instructions
+ playbook
+ task input
```

---

## Principles

* Keep **shared knowledge** in `/context` (no duplication)
* Keep **role behaviour** in `/agents`
* Keep **tasks/workflows** in `/playbooks`
* Keep outputs **structured** via `/schemas`
* Do not hardcode prompts in application code

---

## Summary

* `/context` → facts about the system
* `/agents` → how each role thinks
* `/playbooks` → what task is being performed
* `/schemas` → how results are structured

---
