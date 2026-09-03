# Deployment boundary

The default `docker-compose.yml` is for local evaluation. It intentionally uses development
defaults and must not be exposed to the internet.

`docker-compose.production.yml` is a hardened starting point, not a claim of regulatory or clinical
production readiness. It fails closed when either application secret or the public HTTPS origin is
missing, does not expose the API directly, gives the API a read-only root filesystem, drops Linux
capabilities, and persists application data in a named volume.

## Start a production-like deployment

1. Copy `.env.production.example` to a file kept outside version control.
2. Generate independent high-entropy values of at least 32 characters for `SECRET_KEY` and
   `ADMIN_API_KEY`; the application rejects placeholders, short values, and a shared value.
3. Set `ALLOWED_ORIGINS` to one or more comma-separated exact public HTTPS origins. The application
   rejects HTTP, localhost, credentials, paths, wildcards, queries, and fragments in production.
4. Place a TLS reverse proxy or managed HTTPS load balancer in front of `127.0.0.1:8080`.
5. Run `docker compose --env-file <secure-env-file> -f docker-compose.production.yml up -d --build`.
6. Verify `/health/live`, `/health/ready`, patient workflows, admin authentication, backups, restore,
   logging, monitoring, and security headers before admitting any user.

The bundled web container accepts evidence uploads up to 26 MiB so the proxy boundary is slightly
larger than the API's enforced 25 MiB file limit. It sets a restrictive Content Security Policy,
blocks framing, disables browser camera, microphone, and geolocation features, does not cache the
application shell, and caches only content-hashed build assets. The external TLS proxy remains
responsible for HSTS and public transport security.

## Required work before real patient use

- Replace the shared admin secret with organization identity, role-based authorization, MFA, and
  reviewer-specific audit identity.
- Use an appropriately governed database and encrypted storage; define retention and deletion
  procedures and test encrypted backups and restoration.
- Terminate TLS with a maintained proxy, restrict network ingress, rate-limit sensitive routes, and
  centralize security monitoring without logging question text or patient details.
- Complete threat modeling, dependency and container scanning, penetration testing, incident
  response, privacy impact assessment, accessibility and human-factors testing.
- Obtain accountable legal, privacy, security, clinical-safety, medical-content, and local
  regulatory review for the deployment context.
- Keep all medical sources quarantined until copyright, extraction quality, medical accuracy, and
  patient readability are independently approved.

Never place real patient data, document files, environment files, database volumes, or secrets in
the public repository.
