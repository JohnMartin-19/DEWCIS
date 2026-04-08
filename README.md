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

## Design Decisions

### 1. Database Schema Design

**Two-Table Normalized Structure**

We chose a normalized two-table design for clarity and efficient querying:

- **`archive_runs`**: One row per execution, storing aggregate metrics
  - **Rationale**: Enables quick summary queries without scanning all events
  - **Trade-off**: Requires updating both tables, but simplifies analytics
  - **Status field**: VARCHAR(30) to accommodate "completed_with_errors"

- **`archive_events`**: One row per file operation
  - **Rationale**: Provides complete audit trail for debugging and compliance
  - **Trade-off**: Can grow large, but indexed on `run_id` for fast lookups
  - **Reason field**: TEXT type allows detailed error messages

**Alternative Considered**: Single table with JSON column for events
- Rejected because: Harder to query, no foreign key constraints, poor indexing

### 2. File Handling Strategy

**Move vs Copy**

We use `shutil.move()` instead of copy-and-delete:
- **Rationale**: Atomic operation on same filesystem, faster, less disk usage
- **Trade-off**: Files are removed from source (intentional for archiving)
- **Safety**: Check for duplicates before moving to prevent data loss

**Directory Structure**

Archive layout: `ARCHIVE_DIR/groupname/username/filename`
- **Rationale**: Preserves ownership context, prevents name collisions
- **Trade-off**: Nested structure, but improves organization at scale
- **Consideration**: Easy to restore files to original owner

**Duplicate Handling**

Skip files that already exist at destination:
- **Rationale**: Prevents overwriting potentially different content
- **Trade-off**: No automatic versioning, but safer default behavior
- **Future**: Could implement hash-based deduplication or versioning

### 3. API Architecture

**FastAPI Framework**

Chosen over Flask/Django for:
- **Performance**: Async support, faster response times
- **Type Safety**: Pydantic models provide automatic validation
- **Documentation**: Auto-generated OpenAPI/Swagger docs
- **Modern**: Native async/await support for database operations

**RESTful Endpoint Design**

- `/runs` - Collection resource (LIST)
- `/runs/{id}` - Single resource (GET with nested events)
- `/runs/{id}/files` - Sub-resource with filtering
- `/stats` - Computed resource (denormalized for performance)

**Rationale**: Follows REST conventions, intuitive for clients, cacheable

**Database Connection Strategy**

Direct `psycopg2` connections (not connection pool):
- **Rationale**: Simple for exam, adequate for low-medium traffic
- **Production**: Would use `psycopg2.pool` or SQLAlchemy with connection pooling
- **Trade-off**: Connection overhead per request, but avoids complexity

### 4. Error Handling & Robustness

**Three-State Status Model**

Files can be: `moved`, `skipped`, or `error`
- **Rationale**: Clear distinction between success, intentional skip, and failure
- **Benefit**: Enables filtering queries like "show me all errors"
- **Tracking**: Each state has reason field for debugging

**Run Status**

Runs can be: `running`, `completed`, or `completed_with_errors`
- **Rationale**: Partial success is different from complete failure
- **Benefit**: Dashboard can highlight problematic runs
- **Decision**: Even 1 error marks run as `completed_with_errors`

**Graceful Degradation**

- Missing users → Log warning, continue with other users
- Missing home dirs → Skip user, continue with group
- Database errors → Fail fast with clear error message
- Permission errors → Log per-file, continue with other files

**Rationale**: Maximize successful operations, provide clear feedback

### 5. Testing Strategy

**17-Test Suite Structure**

1. **Database Tests (7)**: Schema, CRUD, connections
2. **Archive Logic Tests (4)**: Group validation, error handling
3. **Integration Tests (3)**: File operations, permissions
4. **Edge Cases (3)**: Special characters, empty dirs, duplicates

**Mocking Strategy**

- Mock system calls (`grp.getgrnam`, `pwd.getpwnam`) for predictability
- Real database for integration tests (testenv provides isolation)
- **Rationale**: Balance between speed and confidence

**Alternative Considered**: All-mocked unit tests
- Rejected because: Wouldn't catch database schema issues or SQL errors

### 6. Packaging & Deployment

**Debian Package Format**

Chose `.deb` over alternatives:
- **Rationale**: Native Linux package manager integration
- **Benefits**: Dependency resolution, clean uninstall, standard format
- **Trade-off**: Platform-specific, but appropriate for target (Linux servers)

**Package Structure**

```
/usr/local/bin/archive-files  # Standard location for custom tools
```

- **Rationale**: Follows FHS, doesn't conflict with system packages
- **Dependencies**: `python3`, `python3-psycopg2` declared in control file
- **Alternative**: Could use Python wheel, but .deb integrates better with apt

**Installation Strategy**

No post-install scripts:
- **Rationale**: Keep it simple, minimal surface area for errors
- **Trade-off**: No automatic database setup, but documented in README
- **Decision**: Admin control over database initialization is better

### 7. LDAP Integration (Part 2)

**ldap3 Library**

Chose `ldap3` over `python-ldap`:
- **Rationale**: Pure Python (no C dependencies), better documentation
- **Benefits**: Easier installation, cross-platform, more Pythonic API
- **Trade-off**: Slightly slower, but negligible for query workload

**Query Strategy**

Two-step process:
1. Query group for members (single LDAP search)
2. Query each member for details (N searches)

**Rationale**: Simple, correct, readable
**Alternative**: Single search with join - more complex, harder to debug
**Trade-off**: N+1 queries, but groups are small (~10 members typical)

### 8. Containerization

**Docker Compose Architecture**

Three services in Part 1:
- **postgres**: Data persistence with health check
- **pgadmin**: Development convenience (not production)
- **testenv**: Isolated test environment with seeded data

**Health Checks**

- PostgreSQL: `pg_isready` before dependent services start
- OpenLDAP: `ldapsearch` with retry logic (slow startup)
- **Rationale**: Prevents race conditions, ensures clean startup

**Volume Strategy**

- Named volume `pgdata`: Persist database across container restarts
- Bind mount `./`: Share code between host and containers
- **Rationale**: Development convenience + data persistence

**testenv Design**

Runs setup script once, then `tail -f /dev/null`:
- **Rationale**: Keep container alive for interactive testing
- **Alternative**: Run script on every start - causes duplicate user errors
- **Solution**: Idempotency marker `/tmp/.setup-done`

### 9. Dashboard Implementation

**Server-Side Rendering**

Single HTML file with embedded CSS/JS:
- **Rationale**: No build step, no framework complexity, works immediately
- **Benefits**: Fast to implement, easy to debug, no dependencies
- **Trade-off**: Not scalable to complex UIs, but sufficient for monitoring dashboard

**Auto-Refresh**

10-second polling with `setInterval`:
- **Rationale**: Simple, works everywhere, no WebSocket complexity
- **Alternative**: Server-Sent Events (SSE) - more efficient but harder
- **Decision**: For exam context, polling is adequate

**Styling**

Inline CSS with cards and tables:
- **Rationale**: Professional appearance without framework overhead
- **Benefits**: Responsive, readable, modern look
- **Trade-off**: Limited reusability, but single-page app

### 10. Configuration Management

**Environment Variables**

All config via env vars (12-factor app principle):
- **Rationale**: Easy to override, works in containers, secure
- **Benefits**: No hardcoded credentials, environment-specific config
- **Pattern**: `os.getenv("VAR", "default")` for fallback

**Defaults Chosen**

- `DB_HOST=postgres`: Container DNS name (works in Docker Compose)
- `ARCHIVE_DIR=/tmp/archive`: Safe default, no permissions needed
- **Rationale**: "Works out of box" in testenv, easy to override for production

### Key Trade-offs Summary

| Decision | Benefit | Trade-off | Accepted Because |
|----------|---------|-----------|------------------|
| PostgreSQL | ACID, relations | Setup overhead | Data integrity critical |
| FastAPI | Speed, modern | Learning curve | Performance + docs |
| Move files | Fast, atomic | Destructive | Archiving intent |
| Normalized schema | Clean, efficient | Two tables | Worth the clarity |
| Two-step LDAP | Simple, clear | N+1 queries | Small groups |
| .deb package | System integration | Platform-specific | Target is Linux |
| Inline CSS | Fast to write | Not reusable | Single page |

### Future Improvements (Out of Scope)

- Connection pooling for API
- Batch file operations for large runs
- Hash-based deduplication
- WebSocket for real-time dashboard updates
- Prometheus metrics export
- Rate limiting on API endpoints
- LDAP connection pooling
- Automated backup procedures

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

MIT License. Test project for DewCIS practical exam.

## Author

John Mburu <johnnkonge2020@gmail.com>

---

**Assessment Date**: April 8, 2026
**Duration**: 2 hours (1.5h Part 1, 0.5h Part 2)
**Status**: ✅ Complete
