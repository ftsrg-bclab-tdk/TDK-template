# Publishing checklist

Copy this file to `PUBLISHING.md` at the repository root when you start preparing the Zenodo
release. From then on, the `hygiene` workflow runs the publication gate (`just hygiene --publish`),
which checks everything a script can check. The items below are the rest. Tick each one and
write the evidence after it: a commit, a file and line, a command and its output, or a link. An
advisor signs the list off by approving the pull request that completes it. `.gitattributes`
keeps this file out of the Zenodo archive.

## Results

- [ ] `just reproduce` regenerates every figure and table in the paper, and `just reproduce --smoke`
      finishes in minutes. Evidence:
- [ ] Recipes are named after their outputs, such as `fig-scalability` or `tab-robustness`. Evidence:
- [ ] The results map has one row per figure and table of the paper, each with its command,
      output path and time on the stated hardware. Evidence:
- [ ] Every dependency is pinned in the `Dockerfile` and the lockfiles. Evidence:

## Metadata

- [ ] The license was agreed with the advisors: Apache 2.0 for a tool, MIT otherwise. Evidence:
- [ ] `related_identifiers` in `.zenodo.json` lists `isDerivedFrom` for a fork's upstream and
      `isSupplementTo` for each paper with a DOI, and nothing else. Evidence:
- [ ] A fork keeps the upstream license, names the upstream authors in `.zenodo.json` and says
      in the README what it changed. Write "not a fork" otherwise. Evidence:
- [ ] A tool has the tool README sections, `MAINTAINERS.md` and `SECURITY.md`. Write "results
      only" otherwise. Evidence:

## Before going public

- [ ] Every history warning of `just hygiene --publish` has been read. The history is not rewritten:
      each warning is either harmless once public or listed here with why it is acceptable. Evidence:
- [ ] Every secret gitleaks ever found has been rotated: the key, token or wallet no longer
      works or holds anything. Evidence:
- [ ] No link points to a same-year TDK paper. Evidence:
- [ ] No AI app or bot is a collaborator or installed app with write access (Settings,
      Collaborators and GitHub Apps). Evidence:
- [ ] A `CLAUDE.md` or `AGENTS.md` that documents the code was renamed, so the archive keeps it.
      Evidence:

## Release (the student's steps, after the pull request merges)

- [ ] The repository and its ghcr.io package are public, and an anonymous
      `docker manifest inspect ghcr.io/<owner>/<repo>:v1.0.0` succeeds. Evidence:
- [ ] Zenodo is enabled for the repository, and release `v1.0.0` is tagged on the commit whose
      results match the paper. Evidence:
- [ ] The Zenodo record's files and metadata are checked, including both supervisors. The
      concept DOI badge in the README resolves. Evidence:
