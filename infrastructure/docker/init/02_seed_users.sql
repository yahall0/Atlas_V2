-- Seed pilot users for development / local testing.
-- Passwords are "atlas2025" (bcrypt-hashed).
-- Uses ON CONFLICT DO NOTHING so re-running is idempotent.

INSERT INTO users (username, password_hash, full_name, role, district, police_station, is_active)
VALUES
  (
    'admin',
    '$2b$12$M0GZyLyHMwJ97TXtN8rWceqZC6NgZf9Sa9luiO3Ldyj3BSgG1D4nu',
    'ATLAS Admin',
    'ADMIN',
    'Ahmedabad',
    NULL,
    TRUE
  ),
  (
    'io_sanand',
    '$2b$12$Kr4pYSDrDCnqmprDmLNXJONzWdpEBxakYNsZaiMdiXcie9yBzPc7i',
    'Sanand IO',
    'IO',
    'Ahmedabad',
    'Sanand',
    TRUE
  ),
  (
    'sho_sanand',
    '$2b$12$QMRP38Xzg.d4g/atPcvCHurKI3gjfEVcj1ZRzDc4MIWbkt5.C2w/C',
    'Sanand SHO',
    'SHO',
    'Ahmedabad',
    'Sanand',
    TRUE
  )
ON CONFLICT (username) DO NOTHING;
