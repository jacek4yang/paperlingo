# Security Policy

## Scope

PaperLingo treats all AI output as untrusted data. The application's security surface
is deliberately small but the following areas are security relevant:

- **Response parsing** (`src/paperlingo/parser/`): JSON extraction and syntax repair
  must never change semantic content or execute anything.
- **HTML rendering**: AI- or user-provided strings must always be escaped or rendered
  as plain text. Injected `<script>`, `<img>`, `<a>`, or `<style>` markup must never
  become active UI.
- **URL handling**: URLs returned by an AI are plain data; only explicit user
  interaction may open them, and only with http/https schemes.
- **File and database handling**: the SQLite database beside the executable, export
  paths, and migration code.

## Supported version

Only the latest release of the `main` branch is supported.

## Reporting a vulnerability

This is a small personal project without a dedicated security contact. If you find a
vulnerability, please open a GitHub issue describing the problem without exploitation
details, or (if disclosure-sensitive) contact the repository owner through GitHub.
Please include reproduction steps and affected versions.
