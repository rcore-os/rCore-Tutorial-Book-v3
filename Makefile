# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?= -W
SPHINXBUILD   ?= sphinx-build
SPHINXAUTOBUILD   ?= sphinx-autobuild
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

html:
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@cp scripts/mermaid.js build/html/_static/

.PHONY: help html Makefile deploy liveview

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

view:
	make html && firefox build/html/index.html

# http://127.0.0.1:8000
liveview:
	@$(SPHINXAUTOBUILD) "$(SOURCEDIR)" "$(BUILDDIR)/html"

deploy:
	@make clean
	@make html
	@cp scripts/mermaid.js build/html/_static/
	@python3 scripts/fix-comments.py
	@rm -rf docs
	@cp -r build/html docs
	@touch docs/.nojekyll
	@git add -A
	@git commit -m "Deploy"
	@git push

htmlpath:
	echo file://$(PWD)/build/html/index.html
