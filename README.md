# DEWCIS - Python Software Developer Practical Assessment

Complete implementation of a file archiving system with REST API, web dashboard, and LDAP integration.

## Overview

This project consists of two parts:
- **Part 1** (2.5 hours): File Archiving System with CLI, PostgreSQL, FastAPI, Dashboard, and Debian package
- **Part 2** (0.5 hours): LDAP Query Script

## Part 1: File Archiving System

### Features

- ✅ CLI script to archive files for Linux group members
- ✅ PostgreSQL database for tracking runs and events
- ✅ FastAPI REST API with 5 endpoints
- ✅ Real-time web dashboard
- ✅ Debian package (.deb) for easy deployment
- ✅ Comprehensive unit tests (17 tests)
- ✅ Docker Compose setup with test environment

### Quick Start

```bash
cd part1

# Start all services
docker compose up -d

# Install the package
docker compose exec testenv dpkg -i /workspace/archive-files_1.0_all.deb

# Run the archiver
docker compose exec -e DB_HOST=postgres testenv archive-files --group developers

# Start the API (from host)
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Access the dashboard at http://localhost:8000

### Architecture

```
┌─────────────────┐
│  archive-files  │  CLI Script (Python)
│   (Debian pkg)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐       ┌──────────────┐
│   PostgreSQL    │◄──────┤   FastAPI    │
│   (archivedb)   │       │   REST API   │
└─────────────────┘       └──────┬───────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │  Dashboard   │
                          │ (HTML/JS)    │
                          └──────────────┘
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/runs` | GET | List all archive runs |
| `/runs/{id}` | GET | Get run details with file events |
| `/runs/{id}/files?status=moved` | GET | Get files for a run (filterable) |
| `/stats` | GET | Overall statistics |

### Database Schema

**archive_runs**
- Tracks each archive run (group, timing, counts, status)

**archive_events**
- Logs each file operation (moved/skipped/error)

### Testing

```bash
# Run all 17 unit tests
docker compose exec -e DB_HOST=postgres testenv python3 /workspace/test_archive_files.py

# Should show: Ran 17 tests in X.XXXs - OK
```

**Test Coverage:**
- Database operations (connections, schema, CRUD)
- Archive logic (group resolution, file moves, errors)
- Edge cases (empty dirs, special chars, duplicates)
- Integration tests (file permissions, directory structure)

### Building the Debian Package

```bash
cd part1

# Package structure is in debian-pkg/
# Build the .deb file
docker compose exec testenv dpkg-deb --build /workspace/debian-pkg /workspace/archive-files_1.0_all.deb

# Install
docker compose exec testenv dpkg -i /workspace/archive-files_1.0_all.deb

# Verify
docker compose exec testenv which archive-files
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | postgres | PostgreSQL hostname |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | archivedb | Database name |
| `DB_USER` | archiveuser | Database user |
| `DB_PASSWORD` | archivepass | Database password |
| `ARCHIVE_DIR` | /tmp/archive | Archive destination |

### Test Environment

The `testenv` container includes:
- **Users**: alice, bob, carol, david, eve, frank, grace
- **Groups**: developers (alice, bob), ops (carol, david), finance (eve, frank), hr (grace)
- **Files**: ~50 test files across user home directories

### Accessing Services

**pgAdmin**
- URL: http://localhost:5050
- Email: admin@dewcis.com
- Password: adminpass

**PostgreSQL** (from host)
```bash
psql -h localhost -p 5433 -U archiveuser -d archivedb
# Password: archivepass
```

## Part 2: LDAP Query Script

### Features

- ✅ Query LDAP directory for group members
- ✅ Display member details (uid, name, home directory)
- ✅ Docker Compose setup with OpenLDAP
- ✅ Pre-seeded test data

### Quick Start

```bash
cd part2

# Start LDAP server
docker compose up -d

# Wait for LDAP to be healthy (~30 seconds)
docker compose ps

# Run query
source venv/bin/activate
python ldap_query.py developers
```

### Usage

```bash
python ldap_query.py <groupname>
```

**Example Output:**
```
Group: developers (gidNumber: 2001)
Members:
  alice | Alice Mwangi | /home/alice
  bob | Bob Otieno | /home/bob
```

### LDAP Structure

```
dc=dewcis,dc=com
├── ou=users
│   ├── uid=alice
│   ├── uid=bob
│   ├── uid=carol
│   └── ...
└── ou=groups
    ├── cn=developers (alice, bob)
    ├── cn=ops (carol, david)
    ├── cn=finance (eve, frank)
    └── cn=hr (grace)
```

### Accessing LDAP Admin

**phpLDAPadmin**
- URL: http://localhost:8090
- Login DN: cn=admin,dc=dewcis,dc=com
- Password: adminpass

### LDAP Connection Details

| Parameter | Value |
|-----------|-------|
| Host | localhost |
| Port | 3389 |
| Base DN | dc=dewcis,dc=com |
| Bind DN | cn=admin,dc=dewcis,dc=com |
| Password | adminpass |

## Project Structure

```
DEWCIS/
├── part1/
│   ├── archive_files.py       # Main archiver script
│   ├── main.py                # FastAPI application
│   ├── test_archive_files.py  # Unit tests
│   ├── docker-compose.yml     # PostgreSQL + testenv
│   ├── setup.sh               # Test environment setup
│   ├── requirements.txt
│   └── debian-pkg/
│       ├── DEBIAN/
│       │   └── control
│       └── usr/local/bin/
│           └── archive-files
│
├── part2/
│   ├── ldap_query.py          # LDAP query script
│   ├── ldap-seed.ldif         # Test data
│   ├── docker-compose.yml     # OpenLDAP + phpLDAPadmin
│   └── requirements.txt
│
└── README.md                   # This file
```

## Development Setup

### Part 1

```bash
cd part1
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
docker compose up -d
```

### Part 2

```bash
cd part2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
docker compose up -d
```

## Troubleshooting

### Container Issues

```bash
# Check status
docker compose ps

# View logs
docker compose logs [service_name]

# Restart
docker compose down && docker compose up -d
```

### Part 1 - Testenv Container Exiting

The testenv container runs a setup script once and then stays alive. If it keeps restarting:

```bash
docker compose logs testenv --tail=50
```

Should see "Test environment ready" once, then container stays up.

### Part 1 - Database Connection Errors

Ensure DB_HOST is set correctly:
- Inside containers: `DB_HOST=postgres`
- From host: `DB_HOST=localhost` with port `5433`

### Part 2 - LDAP Not Ready

LDAP takes ~30 seconds to initialize. Check health:

```bash
docker compose ps openldap
# Should show "healthy" status
```

## Testing Checklist

### Part 1
- ✅ Docker containers running (postgres, pgadmin, testenv)
- ✅ Debian package builds without errors
- ✅ Package installs successfully
- ✅ Archive script runs and moves files
- ✅ Database records are created
- ✅ FastAPI server starts
- ✅ Dashboard loads and shows data
- ✅ All 17 unit tests pass

### Part 2
- ✅ Docker containers running (openldap, ldap-admin)
- ✅ LDAP server is healthy
- ✅ Script queries all groups successfully
- ✅ Member details display correctly

## Performance

### Part 1
- Archive run for 50 files across 7 users: ~1-2 seconds
- API response time: <100ms for most endpoints
- Dashboard auto-refreshes every 10 seconds

### Part 2
- LDAP query response: <50ms
- Supports concurrent queries

## Production Considerations

1. **Security**
   - Use environment secrets for passwords
   - Enable TLS for database and LDAP
   - Implement API authentication
   - Run with least privilege

2. **Scalability**
   - Use connection pooling
   - Add database indexes
   - Implement caching
   - Use message queue for async processing

3. **Monitoring**
   - Log all operations
   - Set up alerts for failures
   - Track metrics (run duration, error rate)
   - Monitor disk usage

4. **Backup**
   - Regular database backups
   - Archive directory backups
   - LDAP directory backups
   - Document restore procedures

## Technologies Used

- **Languages**: Python 3.11+
- **Framework**: FastAPI, Uvicorn
- **Database**: PostgreSQL 15
- **Directory**: OpenLDAP 1.5.0
- **Containerization**: Docker, Docker Compose
- **Packaging**: Debian (.deb)
- **Testing**: unittest

## License

Educational project for DewCIS practical exam.

## Author

John Mburu <john@example.com>

---

**Assessment Date**: April 8, 2026
**Duration**: 3 hours (2.5h Part 1, 0.5h Part 2)
**Status**: ✅ Complete
