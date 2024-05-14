from __future__ import annotations

import contextlib
import datetime
import logging
import os

from collections import defaultdict
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import msgspec
import requests

ROOT = Path(__file__).absolute().parent.parent

IGNORE_AUTHORS = {
    "litestar-org",
    "JacobCoffee",
    "provinzkraut",
    "alc-alc",
    "guacs",
    "peterschutt",
    "cofin",
    "dependabot",
}

IGNORE_REPOS = {
    "litestar-org/litestar",
    "litestar-org/litestar-fullstack",
    "litestar-org/advanced-alchemy",
    "litestar-org/type-lens-docs-preview",
    "litestar-org/type-lens",
    "litestar-org/dtos",
    "litestar-org/polyfactory",
    "cofin/litestar-vite",
    "cofin/litestar-saq",
    "conda-forge/litestar-feedstock",
    "conda-forge/evidently-feedstock",
    "carlsmedstad/aurpkgs",
    "NixOS/nixpkgs",
}


class Repo(msgspec.Struct, rename="camel"):
    name_with_owner: str


class Actor(msgspec.Struct):
    type: str
    login: str


class Comment(msgspec.Struct, rename="camel"):
    updated_at: datetime.datetime


class Comments(msgspec.Struct, rename="camel", frozen=True):
    items: list[Comment] = []
    total_count: int = 0


class Item(msgspec.Struct, rename="camel", kw_only=True):
    type: Literal["Issue", "PullRequest", "Discussion"]
    author: Actor
    url: str
    created_at: datetime.datetime
    last_edited_at: datetime.datetime | None
    closed_at: datetime.datetime | None
    repo: Repo
    number: int
    title: str
    state: Literal["CLOSED", "MERGED", "OPEN", None] = None
    comments: Comments
    reviews: Comments = Comments()


class PageInfo(msgspec.Struct, rename="camel"):
    has_next_page: bool
    end_cursor: str | None = None


class SearchResults(msgspec.Struct):
    class _Search1(msgspec.Struct):
        class _Search2(msgspec.Struct, rename="camel"):
            page_info: PageInfo
            items: list[Item]

        search: _Search2

    data: _Search1


class Commit(msgspec.Struct):
    class Repository(msgspec.Struct):
        full_name: str

    class CommitInfo(msgspec.Struct):
        class Author(msgspec.Struct):
            name: str

        class Committer(msgspec.Struct):
            date: datetime.datetime

        author: Author
        committer: Committer
        message: str

        @property
        def title(self) -> str:
            return self.message.splitlines()[0].strip()

    sha: str
    html_url: str
    node_id: str
    repo: Repository = msgspec.field(name="repository")
    info: CommitInfo = msgspec.field(name="commit")


class CommitSearchResults(msgspec.Struct):
    total_count: int
    items: list[Commit]


class CommitNodesResults(msgspec.Struct, rename="camel"):
    class Data(msgspec.Struct, rename="camel"):
        class CommitNode(msgspec.Struct, rename="camel"):
            class PullRequests(msgspec.Struct, rename="camel"):
                total_count: int

            associated_pull_requests: PullRequests

        nodes: list[CommitNode]

    data: Data


def fetch_recent_items(token: str, after: datetime.datetime) -> list[Item]:
    with requests.Session() as session:
        search = f"litestar updated:>={after.date()}"
        items = []
        # Fetch recent issues, PRs, and discussions
        for file in ["issues.graphql", "discussions.graphql"]:
            with open(ROOT / "github-digest" / file, "r") as f:
                template = f.read()
            cursor = None
            while True:
                params = f'query: "{search}"'
                if cursor is not None:
                    params += f', after: "{cursor}"'

                query = template % params
                resp = session.post(  # type: ignore
                    "https://api.github.com/graphql",
                    headers={"Authorization": f"bearer {token}"},
                    json={"query": query},
                )
                resp.raise_for_status()
                msg = msgspec.json.decode(resp.content, type=SearchResults).data.search
                items.extend(msg.items)
                if msg.page_info.has_next_page:
                    cursor = msg.page_info.end_cursor
                else:
                    break

        # Fetch new repositories that mention Litestar
        query = f"litestar in:name,description,topics created:>={after.date()}"
        resp = session.get(  # type: ignore
            f"https://api.github.com/search/repositories?q={quote(query)}&sort=stars&order=desc",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        repo_search = resp.json()
        for repo in repo_search["items"]:
            created_at = datetime.datetime.strptime(
                repo["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            )
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
            items.append(
                Item(
                    type="Repository",
                    author=Actor(type="User", login=repo["owner"]["login"]),
                    url=repo["html_url"],
                    created_at=created_at,
                    last_edited_at=None,
                    closed_at=None,
                    repo=Repo(name_with_owner=repo["full_name"]),
                    number=repo["id"],
                    title=repo["name"],
                    comments=Comments(),
                )
            )

    return [
        item
        for item in items
        if (
            item.author.login not in IGNORE_AUTHORS
            and item.author.type != "Bot"
            and item.repo.name_with_owner not in IGNORE_REPOS
            and (
                item.created_at >= after
                or (item.last_edited_at is not None and item.last_edited_at >= after)
                or (item.closed_at is not None and item.closed_at >= after)
                or (item.comments.items and item.comments.items[0].updated_at >= after)
                or (item.reviews.items and item.reviews.items[0].updated_at >= after)
            )
        )
    ]


def fetch_recent_commits(token: str, after: datetime.datetime) -> list[Commit]:
    commits: list[Commit] = []

    with requests.Session() as session:
        # Fetch recent commits. This isn't exposed through graphql currently.
        query = quote(f"litestar committer-date:>={after.date()}")
        resp = session.get(  # type: ignore
            (
                f"https://api.github.com/search/commits"
                f"?q={query}&sort=committer-date&order=desc&per_page=100"
            ),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        commit_search = msgspec.json.decode(resp.content, type=CommitSearchResults)

        if commit_search.items:
            filter_commits_with_associated_pr(commit_search, session, token, commits)
    return [
        commit
        for commit in commits
        if commit.info.committer.date >= after
        and commit.info.author.name not in IGNORE_AUTHORS
        and commit.repo.full_name not in IGNORE_REPOS
    ]


def filter_commits_with_associated_pr(commit_search, session, token, commits):
    """Filter out commits that have an associated PR."""
    node_ids = [commit.node_id for commit in commit_search.items]

    # Filter out commits that have an associated PR. This can only be
    # done by graphql.
    with open(ROOT / "github-digest" / "commits.graphql", "r") as f:
        template = f.read()
    query = template % msgspec.json.encode(node_ids).decode()
    resp = session.post(  # type: ignore
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {token}"},
        json={"query": query},
    )
    resp.raise_for_status()
    nodes = msgspec.json.decode(resp.content, type=CommitNodesResults).data.nodes
    for commit, node in zip(commit_search.items, nodes):
        if node.associated_pull_requests.total_count == 0:
            commits.append(commit)


def format_embed(groups: dict[str, list[Item | Commit]]) -> dict:
    embed = {
        "title": "GitHub Search Digest: `litestar`",
        "description": "Recent activity in the Litestar ecosystem",
        "color": 0xEDB641,
        "thumbnail": {
            "url": "https://raw.githubusercontent.com/litestar-org/branding/main/assets/Branding%20-%20PNG%20-%20Transparent/Badge%20-%20Blue%20and%20Yellow.png"  # noqa: E501
        },
        "footer": {"text": "I run daily at 1400UTC (9PM Central)"},
        "fields": [],
    }

    for repo, items in sorted(groups.items()):
        field_value = ""
        for item in items:
            if isinstance(item, Item):
                if item.type == "Repository":
                    field_value += f"- [New Repository]({item.url}): {item.title}\n"
                else:
                    label = "PR" if item.type == "PullRequest" else item.type
                    field_value += (
                        f"- [{label} #{item.number}]({item.url}): {item.title}\n"
                    )
            else:
                field_value += (
                    f"- [Commit {item.sha[:8]}]({item.html_url}): {item.info.title}\n"
                )

        embed["fields"].append({"name": repo, "value": field_value, "inline": False})

    logging.debug("Formatted embed before sending: %s", embed)
    return embed


def send_webhook(webhook_url: str, embed: dict) -> None:
    payload = {"embeds": [embed]}
    logging.debug("Payload to send: %s", payload)
    response = requests.post(webhook_url, json=payload)
    if response.status_code != 204:
        logging.error("Failed to send webhook: %s", response.content)
    response.raise_for_status()


def main() -> None:
    with contextlib.suppress(FileNotFoundError):
        with open(ROOT / ".env", "r") as f:
            for line in f:
                key, val = line.strip().split("=", 1)
                val = val.removeprefix('"').removesuffix('"')
                os.environ[key] = val

    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
    DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=14)
    after = datetime.datetime.combine(
        yesterday, datetime.time(14, tzinfo=datetime.timezone.utc)
    )

    items = fetch_recent_items(GITHUB_TOKEN, after)
    commits = fetch_recent_commits(GITHUB_TOKEN, after)

    if items or commits:
        groups: defaultdict[str, list[Item | Commit]] = defaultdict(list)
        for item in items:
            groups[item.repo.name_with_owner].append(item)
        for commit in commits:
            groups[commit.repo.full_name].append(commit)
        embed = format_embed(groups)

        logging.debug("Formatted embed before sending: %s", embed)
        send_webhook(DISCORD_WEBHOOK_URL, embed)


if __name__ == "__main__":
    main()
