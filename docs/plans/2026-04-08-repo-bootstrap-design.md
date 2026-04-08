# Repo Bootstrap Design

## Goal
Make the repository publishable and easier to collaborate on by initializing git, adding a project-level `README.md`, and adding an MIT `LICENSE`.

## Context
- The workspace is currently not a git repository.
- The root does not contain a project `README*`.
- The root does not contain a project `LICENSE`.
- The project already has working Python environment metadata via `uv`, plus verified scripts and tests.
- The user explicitly chose MIT over GPLv3 because they prefer a permissive open-source posture.

## Decision
- Initialize git in the current workspace root.
- Add a concise but repo-specific `README.md`.
- Add a standard MIT `LICENSE`.
- Do not add extra repository-management files such as CI, `CONTRIBUTING.md`, or changelog yet.
- Do not create a commit unless the user asks for one.

## README Scope
The `README.md` should cover only the highest-value onboarding information:
- what the repo is
- current capabilities
- supported workflow commands
- `uv` setup
- important current behavior boundaries
- MIT license note

It should not duplicate all internal planning documents.

## Git Scope
Git initialization should be minimal:
- create `.git/`
- leave working tree unchanged otherwise
- do not create commits or configure remotes

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| README becomes generic marketing copy | Medium | Keep it repo-specific and command-driven |
| License text mismatches user intent | Low | Use standard MIT text only |
| Git init surprises user by creating commits | Low | Initialize repo only, no commit |

## Key Principle
Bootstrap only the minimum public-facing repository surface that clarifies what this project is and how to run it.
