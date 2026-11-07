# Paper commands run in the component directory; generic automation stays at the root.
.DEFAULT_GOAL := all
PAPER_TARGETS := all draft final check check-final check-submit fix fix-dry fix-review skeleton essentials guide-bib test test-lint test-review test-layout
.PHONY: $(PAPER_TARGETS) paper-proxies clean clean-proxies
$(PAPER_TARGETS):
	$(MAKE) -C paper $@
lint-%:
	$(MAKE) -C paper $@
paper-proxies:
	latexmk -xelatex -shell-escape -interaction=nonstopmode paper-draft.tex paper-final.tex

clean: clean-proxies
	$(MAKE) -C paper clean
clean-proxies:
	latexmk -C paper-draft.tex paper-final.tex
	rm -rf _minted _minted-paper-draft _minted-paper-final svg-inkscape
	rm -f paper-draft.tdo paper-final.tdo paper-draft.lol paper-final.lol paper-draft.thm paper-final.thm
