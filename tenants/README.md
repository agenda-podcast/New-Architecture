# Tenants

Per-tenant artifacts (commit-friendly).

Layout:

```
tenants/<TENANT_ID>/
  outputs/<topic_id>/...   # scripts, images, audio, prepared images, videos
  data/<topic_id>/...      # per-topic caches (optional)
```

Enable by setting `TENANT_ID` (and optionally `USE_TENANT_OUTPUTS=true`).
