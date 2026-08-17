# dependency-gate

A composite GitHub Action that flags dependencies a pull request newly introduces
and requires an explicit human sign-off label before the pull request can merge.

It answers one security question: *was the provenance of this package checked before
it became a dependency?* It does not judge whether a package is trustworthy. It makes
a new package impossible to merge unnoticed, and records who accepted it.

## Usage

```yaml
name: New dependency gate

on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]

permissions:
  contents: read
  pull-requests: write

jobs:
  new-dependency-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
        with:
          fetch-depth: 0
      - uses: velocity-exchange/dependency-gate@v1
        with:
          lockfiles: bun.lock ui/bun.lock
```

`fetch-depth: 0` is required. The action compares against the base commit, which is
not present in a shallow clone.

Trigger on `labeled` and `unlabeled` as well as the usual events, or applying the
label will not re-run the check that the label is meant to satisfy.

### Inputs

| Input | Default | Description |
| --- | --- | --- |
| `lockfiles` | required | Space-separated, repo-relative lockfile paths to watch. |
| `label` | `deps-reviewed` | Label recording sign-off on the new packages. |
| `comment` | `true` | Post or update a sticky comment listing new packages. |
| `token` | `github.token` | Token used to read labels and write the comment. |

### Outputs

| Output | Description |
| --- | --- |
| `count` | Number of newly added packages. |
| `packages` | Tab-separated `lockfile<TAB>package` lines. |

## Supported lockfiles

`bun.lock`, `yarn.lock` (v1 classic and berry), `pnpm-lock.yaml`, `Cargo.lock`,
`uv.lock`.

Files are dispatched by filename, so the path may be nested but the basename must
be one of the above. `bun.lockb` is bun's binary format and is not supported;
convert it to the text `bun.lock` format to gate it.

The parser reads text only. It never installs, resolves, or reaches the network, so
it is safe to run against a lockfile from an untrusted pull request.

## Why the parser lives here

The obvious implementation puts the script in each repository, next to the workflow.
That has a hole: on a `pull_request` event the workflow runs against the merge commit,
so the script is the pull request's own copy. A pull request can add a dependency and
edit the script that is supposed to report it, in the same diff, and the check passes.

Shipping the parser inside the action removes it from the pull request's editable
surface. Callers reference it by tag or commit SHA, and the code that runs is the code
in this repository.

One gap remains and cannot be closed from here: the *calling workflow* is still read
from the pull request's ref, so a pull request can edit or delete its own gate. Closing
that needs repository configuration rather than code:

- require this check via a branch ruleset, so removing the job blocks the merge, and
- require review on `.github/**` via CODEOWNERS.

## Behaviour outside a pull request

On a `push` event the action reports to the job summary and never fails, since there
is nothing to label. This is useful where an automation commits dependency bumps
straight to a branch, so the change is at least recorded.

## Fork pull requests

A pull request from a fork gets a read-only token, so commenting fails. The action
downgrades that to a warning and still enforces the label, rather than aborting before
the check it exists to perform.

## Development

```bash
python3 tests/test_parser.py
```

No third-party packages. A dependency gate that needed its own dependency tree would
be a poor advertisement for itself.

When changing the parser, add a case to `tests/test_parser.py` first. Every consumer
repository pins this action, so a defect here reaches all of them at once.
