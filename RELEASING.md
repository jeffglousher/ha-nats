# Community release gate

This is a release candidate; a build is not evidence that all release gates pass.
Before making a repository public or publishing a release:

- Review the complete Git history for credentials, private deployment notes and
  third-party material. Current files being clean is not sufficient.
- Confirm the wrapper license, third-party notices and artwork attribution.
- Pass manifest checks and native amd64/arm64 image builds and runtime tests.
- Review the image/dependency vulnerability scan; document or fix findings.
- Test a fresh install through the repository URL on Home Assistant OS, plus an
  in-place upgrade and cold backup/restore in a disposable installation.
- For NUI, test a fresh browser through ingress, including live WebSockets and
  rejection of anonymous/direct access. For NATS, test authenticated clients,
  invalid credentials, persistent streams and consumer recovery.
- Verify Documentation, Info, Configuration, Log, icons and update behavior in HA.
- Enable private vulnerability reporting and protect the default branch.
- Tag the reviewed commit with the app version and publish release notes with
  tested platforms, known limits and migration guidance.

Repository-based installation has a different app identity from local development
installation. Never uninstall a local app merely to change its source: back up
and migrate data explicitly. Keep the old backup until restoration is verified.

Do not describe these apps as official Home Assistant, NATS or NUI projects.

## Free GitHub checks for public repositories

The workflows use standard hosted runners and read-only default permissions.
Dependency review rejects newly introduced vulnerabilities at every severity,
including development dependencies. It runs on pull requests in public repos;
a skipped private-repository job is not a successful scan. Image scanning remains
necessary because the dependency graph does not cover every container package.
CodeQL covers the wrapper Python and Actions, not upstream source fetched inside
a Docker build. Clippy and MIRAI do not apply to these non-Rust wrappers.

After publication, verify these repository settings and results:

- Enable secret scanning, push protection and private vulnerability reporting.
- Keep Dependabot alerts and automated security updates enabled.
- Require successful Release checks, CodeQL and Dependency review on pull requests.
  Select actual completed check names; do not infer success from workflow files.
- Protect main against deletion and force pushes; require changes through PRs.
- Confirm fork PR checks work without repository secrets or write tokens.
- Re-run native builds and runtime tests on both supported architectures.

Publishing source and tagging a stable app release are separate decisions.
Do not tag a stable release until the installation and recovery gates above pass.
