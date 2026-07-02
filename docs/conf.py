# SPDX-License-Identifier: Apache-2.0
"""Sphinx configuration for the ccsds-data-messages documentation."""

from importlib.metadata import version as _distribution_version

# -- Project information -----------------------------------------------------

project = "ccsds-data-messages"
author = "Loft Orbital Solutions Inc."
copyright = "Loft Orbital Solutions Inc."  # noqa: A001

# The version is derived from the installed distribution, which hatch-vcs sets
# from the git tag, so there is nothing to keep in sync by hand.
release = _distribution_version("ccsds-data-messages")
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinxcontrib.autodoc_pydantic",
]

# The Makefile passes -W, so any warning (a missing toctree entry, a broken
# cross-reference, a failed autodoc import) fails the build. Nitpicky mode is left
# off on purpose: it would flag every internal type alias and TypeVar in the
# annotations (FieldMetadata, TypeVars, and so on), which are not documented targets.
templates_path = ["_templates"]
# gaps.md lives in this directory as a working document but is intentionally not part
# of the published site, so it is excluded from the source tree Sphinx processes.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "gaps.md"]

# Markdown pages carry their own top-level heading, so let a document start
# below h1 without a warning.
myst_heading_anchors = 3

# -- Autodoc / Napoleon ------------------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = False

autodoc_typehints = "description"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}

# autodoc_pydantic: show the field documentation but hide the config and
# validator machinery, which is noise for a reader of the public API.
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_summary = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_field_list_validators = False
autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_member_order = "bysource"

# -- Intersphinx -------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
}

# -- HTML output -------------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_title = "ccsds-data-messages"

# Custom CSS widens the RTD content area and normalizes the sidebar font size
# across toctree depths (the stock theme shrinks l3/l4 entries).
html_static_path = ["_static"]
html_css_files = ["custom.css"]
