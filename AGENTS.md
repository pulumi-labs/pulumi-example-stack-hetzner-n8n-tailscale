# Private n8n example

- Runtime is Python Pulumi, cloud-init, native systemd and Docker Compose.
- Keep applications unpublished on the host and n8n bound to sidecar loopback.
  Serve is HTTPS inside the existing tailnet, with no Funnel or policy writes.
- Keep PostgreSQL roles separate and workflow SQL parameterized.
- Read config once. All image references require genuine reviewed digest pins.
  Generate dependency locks and scan the exact closure in the approved sandbox.
- Never execute/install dependencies, providers, containers or workload checks on
  the workstation. Source-only review is not deployment validation.
- Native acceptance scripts and evidence belong in the run directory.
- Keep credentials, state, real configuration and private logs outside this tree.
- Export and private publication require applicable owner authorization. Keep the
  repository private until separately reviewed and approved for public release.
- Do not choose an authored-code license or change shared accounts without
  applicable owner authorization.
