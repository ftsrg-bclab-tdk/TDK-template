DOCUMENT=draft
LATEXMK=latexmk -xelatex -shell-escape -interaction=nonstopmode
LINT=texlua scripts/lint.lua

all: draft

# The draft, with todos, beats and the guide.
draft:
	$(LATEXMK) $(DOCUMENT).tex

# The paper as the reviewer sees it: no notes, no list of todos, no guide. This is the PDF to upload.
# "final" names this format, not the state of the paper: make check-submit says whether it is ready.
final:
	$(LATEXMK) final.tex

clean:
	latexmk -C $(DOCUMENT).tex final.tex
	rm -rf _minted _minted-$(DOCUMENT) _minted-final svg-inkscape *.tdo *.lol *.thm lint-checks.tex content/*.aux guide/*.aux include/*.aux

# The requirements table's rows with a rule name (guide, Requirements): every lint rule against the draft build.
# "make lint-<rule>" runs one; "texlua scripts/lint.lua list" names them.
check:
	$(LINT) all --doc $(DOCUMENT)

lint-%:
	$(LINT) $*

# The fixes the lint suggests (scripts/lint/fixes.lua): fix writes the safe ones and prints the
# diff, fix-dry only prints it, fix-review writes the ones to read first as well. Placeholders are
# never written: the lint prints them, you fill in their holes.
fix:
	$(LINT) fix

fix-dry:
	$(LINT) fix --dry-run

fix-review:
	$(LINT) fix --review

# The same against the final build, which is the one the page count and the todos are judged on.
check-final: final
	$(LINT) all --doc final

# The check before you upload: the final build against every rule at the submit phase, whatever
# \lintphase says. The final PDF hides todos and gap markers, so how it looks says nothing.
check-submit: final
	$(LINT) all --doc final --phase submit

# The lint's copy of the skeleton chapters (scripts/lint/skeleton), after editing content/01-07 of the template.
skeleton:
	mkdir -p scripts/lint/skeleton && cp content/0[1-7]-*.tex scripts/lint/skeleton/

# The guide's reference of the essentials (guide/essentials.tex), after editing scripts/lint/essentials.lua.
essentials:
	$(LINT) essentials --guide > guide/essentials.tex

# The guide's own reference list, guide/guide.bbl, after editing its citations or guide/guide.bib.
guide-bib:
	texlua scripts/guide-bib.lua

# The template's regression suites, also run by CI. Requires TeX Live and PyMuPDF;
# mutation tests need make final first. Use a Python environment with PyMuPDF installed.
test: test-lint test-review test-layout

test-lint:
	python3 scripts/lint/tests/mutations.py
	python3 scripts/lint/tests/execution.py
	python3 scripts/lint/tests/ci.py
	python3 scripts/lint/tests/evidence.py
	python3 scripts/lint/tests/safety_readers.py

test-review:
	python3 -m unittest scripts/review/test_review.py scripts/skim/test_skim.py

.PHONY: all draft final clean check check-final check-submit fix fix-dry fix-review guide-bib skeleton essentials test test-lint test-review

# Git-root hygiene and agent lookup must work from the nested component.
test-layout:
	python3 -m unittest discover -s scripts/tests -v
.PHONY: test-layout
