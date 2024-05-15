# Automations

[![CI](https://github.com/jcrist/automations/actions/workflows/ci.yml/badge.svg)](https://github.com/jcrist/automations/actions/workflows/ci.yml)

Creates a digest of the latest goings-on for a repo and posts it to Discord
via a given webhook.

~~Stolen~~ Inspired by [@jcrist](https://github.com/jcrist/automations/) :)

## Setup

1. Clone
2. Set up `DISCORD_COMMUNITY_WEBHOOK_URL`, `DISCORD_MAINTAINER_WEBHOOK_URL` secrets
3. Run CLI or CI

> [!NOTE]
> [Makefile](Makefile) is provided for convenience.

## Usage

Help:
```console
python ./github-digest/main.py --help
```

Common Usage:

Specify Terms:
```console
python ./github-digest/main.py --term litestar --term blarg
```

Specify new webhook:
```console
python ./github-digest/main.py --webhook https://discord.com/api/webhooks/1234567890/ABCDEF
```

Full Help:
```console
➜ python github-digest/main.py --help
Usage: c-l-i [-t TERM] [-d] [--token TOKEN] [--webhook WEBHOOK] [--age AGE] [-h] [--completion COMPLETION]

  GitHub Daily Digest CLI.

  Options
    [-t, --term TERM]          The search term(s) to use for fetching recent items and commits. Valid options: litestar, polyfactory, advanced-alchemy.
    [-d, --debug]              Enable debug mode. Checks the DEBUG environment variable if not provided.
    [--token TOKEN]            The GitHub API token to use for fetching data.
    [--webhook WEBHOOK]        The Discord webhook URL to send the daily digest to.
    [--age AGE]                The age of the data to fetch in days. Defaults to 1 day.

  Help
    [-h, --help]               Show this message and exit.
    [--completion COMPLETION]  Use `--completion generate` to print shell-specific completion source. Valid options: generate, complete.
```

## Example

![Example](example.png)
