# Minimal makefile for Sphinx documentation
#
.DEFAULT_GOAL := all

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Make sure color is used to generate SVG files. The 'Read the Docs' builder
# sets NO_COLOR (without a by-your-leave), which is rather unhelpful. Here we
# undefine it and set FORCE_COLOR for good measure.
undefine NO_COLOR
export FORCE_COLOR = 1

svg_files = $(patsubst %.snip, %.svg, $(wildcard snippet-examples/file_format/*.snip))

%.svg: %.snip
	snippets --svg=$@ $<

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
html: Makefile $(svg_files)
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
