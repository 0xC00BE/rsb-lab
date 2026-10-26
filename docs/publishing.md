# Publishing this source preview

Target repository: `0xC00BE/rsb-lab`. Do not publish the parent private workspace.
The source-preview folder is the repository root. Review its staged files and
validation report, then publish **v0.1.0-preview.2** as a prerelease.

If using the GitHub CLI, authenticate normally and run from this repository:

```bash
gh auth status
gh repo create 0xC00BE/rsb-lab --public --source=. --remote=origin --push
git tag -a v0.1.0-preview.2 -m "RSB Brewery ICS Lab VMware reference preview"
git push origin v0.1.0-preview.2
gh release create v0.1.0-preview.2 --repo 0xC00BE/rsb-lab --prerelease \
  --title "RSB Brewery ICS Lab v0.1.0-preview.2" --notes-file RELEASE_NOTES.md
```

If the local repository already has an origin URL, omit `--remote=origin` when
creating the GitHub repository or create the remote repository first and push
normally. If the repository already exists on GitHub, inspect its contents before
pushing; never force-push over unrelated work.

If the local preview tag already exists, do not recreate it. GitHub automatically
provides source archives for the tag. The separately prepared sanitized ZIP and
SHA-256 file can be attached as release assets. Do not attach build scratch files,
validation executables, `.env`, local state, or private lab exports.

The first stable release should follow a clean build and acceptance report on a
second machine. Prerelease publication is useful for community porting, but must
retain the limitations in the README and release notes.
