# Minimal makefile for Sphinx documentation
#
.DEFAULT_GOAL := all

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build
export CLIPPETS_EDITOR =

snip_files += $(wildcard getting-started/first-run/*.snip)
snip_files = $(wildcard reference/file_format/*.snip)
snip_files += $(wildcard user-guide/basics/*.snip)
snip_files += $(wildcard user-guide/editing/*.snip)
snip_files += $(wildcard user-guide/groups/*.snip)
snip_files += $(wildcard user-guide/moving/*.snip)

svg_files = $(patsubst %.snip, %.svg, $(snip_files))

sources = $(wildcard ../src/clippets/*.py)
sources += $(wildcard ../src/clippets/*.css)

$(svg_files) : $(sources)

%.svg: %.snip
	snippets --work-dir=svg-gen --svg=$@ $<

getting-started/first-run/first-run.svg: $(sources)
	snippets --dims=80x24 --work-dir=svg-gen --svg=$@ snippets.txt

readme_files = mk_readme.py README.txt credits.txt

../README.rst : $(readme_files)
	python mk_readme.py

all: $(svg_files) ../README.rst html

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile all

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
html: Makefile $(svg_files) getting-started/first-run/first-run.svg
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
