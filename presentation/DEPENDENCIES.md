# Dependency triage

Checked on 3 November 2026 against `package-lock.json`, `npm audit --json`, the
linked advisories, and the installed call sites below. Compatible transitive
updates have been applied. The remaining audit entries represent five advisories
in four packages; counts also include their dependants. They execute in build
tooling, so the `devDependency` label does not make them harmless.

| Installed package / advisory | Trigger and relevance to this build | Remediation |
| --- | --- | --- |
| `basic-ftp` 5.3.1, [GHSA-c475-qrg2-pj4r](https://github.com/advisories/GHSA-c475-qrg2-pj4r) | A malicious FTP directory listing can consume excessive CPU. The installed `get-uri/dist/ftp.js` calls `Client.list()` when fetching an FTP resource if modification-time lookup fails. Here it is a dependency of the browser downloader's proxy/PAC stack. The supplied deck uses local resources and an installed browser; no FTP/PAC fetch is configured. Reassess if adding browser downloads or FTP-backed proxy configuration. This is not evidence that arbitrary remote slide resources are safe. | Fixed in 6.2.1, outside `get-uri`'s `^5.0.2` range. No compatible fix in the currently supported chain. Keep local browser discovery; update when upstream adopts a fixed FTP dependency. |
| `extract-zip` 2.0.1, [GHSA-jmr9-qjv8-65gv](https://github.com/advisories/GHSA-jmr9-qjv8-65gv) and [GHSA-7pqw-9j4j-h8q3](https://github.com/advisories/GHSA-7pqw-9j4j-h8q3) | Crafted ZIP symlinks can escape the extraction destination, including arbitrary writes. `@puppeteer/browsers/lib/cjs/fileUtil.js` imports it to unpack browser archives. These scripts launch an installed executable; they do not download/unpack browsers or user ZIPs. `npm ci --ignore-scripts` also avoids install hooks. Adding an automatic browser installer would change this assessment. | The advisories list no patched `extract-zip` release. Puppeteer 25 offers a newer dependency chain, but Marp 4.5.1 requires Puppeteer `^24.43.1`. Wait for supported upstream adoption; do not force Puppeteer 25 into Marp. |
| `zod` 3.25.76, [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) | Oversized invalid collections can exhaust memory while validation accumulates errors. Installed through `chromium-bidi`'s protocol parsers. The checker launches local Chrome with Puppeteer's default CDP path, not a user-facing schema-validation service. No WebDriver BiDi input endpoint is exposed by these scripts. Reassess if using Firefox/BiDi, remote browser connections, or direct Zod validation of untrusted inputs. | Fixed in 4.6.6, outside the installed BiDi parser's Zod 3 range. No supported compatible update found. Upgrade with the Marp/Puppeteer chain when it supports the fixed parser. |
| `katex` 0.17.0, [GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7) | Requires prior prototype pollution or attacker-controlled options prototypes, attacker-controlled math, and insertion of the rendered output without separate sanitization. It can then bypass trust restrictions. Generated frontmatter sets `math: false`; the starter has no math. Rendering untrusted content or enabling math requires a new assessment. | Fixed in 0.18.2, outside Marp Core 4.4.0's `^0.17.0` range. Keep math disabled until a compatible Marp release adopts the fix, or separately evaluate a supported renderer change. |

These reachability assessments are inferences from the current scripts and
installed dependency code, not exploit tests or claims that the packages are
universally safe. Marp CLI 4.5.1 and Core 4.4.0 were the registry's latest releases
at this check. `npm audit fix --force` proposes unsupported major changes or an
obsolete Marp downgrade, so it was not used. Repeat the audit after upstream
updates, then rebuild HTML/PDF/PNGs and rerun the rendering checks before changing
the lockfile.

## Actual build and CI boundary

Marp accepts inline HTML and local file access to render this design. Treat a
changed deck, theme, or build script as executable/untrusted input, regardless of
these advisories. Local builds should use reviewed sources, without production
credentials in the environment. The offline-resource check runs after the build;
it is a portability check, not a sandbox for the earlier render.

The presentation workflow uses a GitHub-hosted ephemeral runner, a read-only
GitHub token, no persisted checkout credential, no project secrets, and a
10-minute job limit. It uses `pull_request`, not `pull_request_target`, and an
already installed Chrome browser. No BME or other persistent self-hosted runner
is selected. These controls limit exposure and runaway jobs; they do not patch
the dependencies or make arbitrary PR code safe on a personal machine.
