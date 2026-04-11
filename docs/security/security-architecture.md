# ATLAS Security Architecture

## Authentication: JWT (HS256) with role-based access control
## Encryption: AES-256 at rest, TLS 1.3 in transit
## RBAC: 6 roles (IO, SHO, DySP, SP, Admin, Read-only) with district-scoped data
## PII: Auto-detected by OCR pipeline (mobile, Aadhaar, address), flagged for redaction
## Audit: Append-only PostgreSQL table, every API request logged
## Compliance: DPDP Act 2023, Bharatiya Sakshya Adhiniyam 2023
