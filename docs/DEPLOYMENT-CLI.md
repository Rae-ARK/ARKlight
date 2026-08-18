# Deployment Design

## Goal

`arklight deploy` provides a thin deployment interface for built static sites.

Cloudflare Workers is the default deployment target. ARKlight does not implement provider-specific deployment infrastructure. It delegates deployment to the provider's official CLI.

## CLI

### Default: Cloudflare Workers

```bash
arklight deploy
````

Equivalent to:

```bash
arklight deploy cloudflare
```

The Cloudflare deployment path:

1. Build the ARKlight site.
2. Verify that Wrangler is available.
3. Invoke the appropriate `wrangler deploy` command.
4. Hand control to Wrangler.
5. Do not reimplement Cloudflare authentication, uploading, configuration, or deployment management.

Wrangler is responsible for the actual Cloudflare deployment.

### Explicit provider

```bash
arklight deploy cloudflare
```

### Future providers

Other deployment targets must be exposed through explicit provider flags or subcommands, for example:

```bash
arklight deploy --github
arklight deploy --netlify
arklight deploy --vercel
```

The exact providers and flags are not part of the current implementation and should only be added when their deployment integrations are designed.

## Provider Boundary

ARKlight owns:

```text
Python source
    ↓
ARKlight compilation/build
    ↓
static site / deployment artifact
```

The deployment provider owns:

```text
deployment artifact
    ↓
provider CLI
    ↓
hosting platform
```

ARKlight must remain a thin orchestration layer.

Do not embed provider APIs, authentication systems, upload protocols, or provider-specific deployment logic into the core compiler.

## Wrangler Requirement

ARKlight must not silently install Wrangler.

If Wrangler is unavailable, fail with a clear message explaining that Wrangler is required and that the user must install/configure it separately.

Once ARKlight invokes Wrangler, Wrangler owns the deployment process and its output should be forwarded normally.

## Design Principle

`arklight deploy` should make deployment convenient without making ARKlight responsible for operating every hosting platform.

Cloudflare Workers is the default because it is the primary supported deployment target, not because ARKlight should become a Cloudflare SDK.

```
