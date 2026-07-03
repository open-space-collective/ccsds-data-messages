# Security Policy

## Supported versions

`ccsds-data-messages` is pre-1.0. Security fixes are applied to the latest
released version on PyPI. Please upgrade to the latest release before reporting.

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a public
issue. Use GitHub's [private vulnerability reporting][gh-advisory] on this
repository ("Security" tab > "Report a vulnerability").

Please include:

- a description of the vulnerability and its impact,
- steps to reproduce (a minimal message or code snippet is ideal),
- the library version and Python version.

We will acknowledge your report within 5 business days and aim to provide a
resolution or mitigation timeline within 30 days.

## Scope

This library parses untrusted message content. XML is parsed with
[`defusedxml`][defusedxml] to mitigate entity-expansion and external-entity
attacks. Reports of parser denial-of-service, resource-exhaustion, or any path
that bypasses those protections are in scope and especially welcome.

[gh-advisory]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability
[defusedxml]: https://pypi.org/project/defusedxml/
