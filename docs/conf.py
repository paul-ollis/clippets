# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from sphinx.highlighting import lexers
from snippet_lexer import CustomLexer

# -- Project information -----------------------------------------------------

pygments_style = 'lovelace'
lexers['snippets'] = CustomLexer(startinline=True)

project = 'Clippets'
copyright = '2023, Paul Ollis'
author = 'Paul Ollis'
release = '0.4'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
