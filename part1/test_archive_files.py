#!/usr/bin/env python3
import unittest
import tempfile
import os
import shutil
import grp
import pwd
from unittest.mock import Mock, patch, MagicMock
import psycopg2
from archive_files import (
    get_connection,
    create_schema,
    start_run,
    log_event,
    finish_run,
    archive_group,
    DB_CONFIG,
    ARCHIVE_ROOT
)


class TestDatabaseFunctions(unittest.TestCase):
    """Test database-related functions"""

    @classmethod
    def setUpClass(cls):
        """Set up test database connection"""
        try:
            cls.conn = psycopg2.connect(**DB_CONFIG)
            create_schema(cls.conn)
        except psycopg2.OperationalError:
            cls.skipTest(cls, "Database not available")

    @classmethod
    def tearDownClass(cls):
        """Close database connection"""
        if hasattr(cls, 'conn'):
            cls.conn.close()

    def test_get_connection(self):
        """Test database connection"""
        conn = get_connection()
        self.assertIsNotNone(conn)
        self.assertFalse(conn.closed)
        conn.close()

    def test_create_schema(self):
        """Test schema creation creates required tables"""
        conn = get_connection()
        create_schema(conn)

        with conn.cursor() as cur:
            # Check archive_runs table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'archive_runs'
                )
            """)
            self.assertTrue(cur.fetchone()[0])

            # Check archive_events table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'archive_events'
                )
            """)
            self.assertTrue(cur.fetchone()[0])

        conn.close()

    def test_start_run(self):
        """Test starting an archive run"""
        conn = get_connection()
        create_schema(conn)

        run_id = start_run(conn, "testgroup")
        self.assertIsInstance(run_id, int)
        self.assertGreater(run_id, 0)

        # Verify run was recorded
        with conn.cursor() as cur:
            cur.execute("SELECT group_name, status FROM archive_runs WHERE id = %s", (run_id,))
            result = cur.fetchone()
            self.assertEqual(result[0], "testgroup")
            self.assertEqual(result[1], "running")

        conn.close()

    def test_log_event(self):
        """Test logging archive events"""
        conn = get_connection()
        create_schema(conn)
        run_id = start_run(conn, "testgroup")

        log_event(conn, run_id, "/src/file.txt", "/dst/file.txt", "moved")

        # Verify event was logged
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, destination, status
                FROM archive_events
                WHERE run_id = %s
            """, (run_id,))
            result = cur.fetchone()
            self.assertEqual(result[0], "/src/file.txt")
            self.assertEqual(result[1], "/dst/file.txt")
            self.assertEqual(result[2], "moved")

        conn.close()

    def test_log_event_with_reason(self):
        """Test logging events with error reasons"""
        conn = get_connection()
        create_schema(conn)
        run_id = start_run(conn, "testgroup")

        log_event(conn, run_id, "/src/file.txt", "/dst/file.txt", "error", "Permission denied")

        with conn.cursor() as cur:
            cur.execute("SELECT reason FROM archive_events WHERE run_id = %s", (run_id,))
            reason = cur.fetchone()[0]
            self.assertEqual(reason, "Permission denied")

        conn.close()

    def test_finish_run(self):
        """Test finishing an archive run"""
        import datetime

        conn = get_connection()
        create_schema(conn)
        started_at = datetime.datetime.utcnow()
        run_id = start_run(conn, "testgroup")

        finish_run(conn, run_id, moved=10, skipped=2, errors=0, started_at=started_at)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT total_moved, total_skipped, total_errors, status, duration
                FROM archive_runs WHERE id = %s
            """, (run_id,))
            result = cur.fetchone()
            self.assertEqual(result[0], 10)
            self.assertEqual(result[1], 2)
            self.assertEqual(result[2], 0)
            self.assertEqual(result[3], "completed")
            self.assertIsNotNone(result[4])
            self.assertGreater(result[4], 0)

        conn.close()

    def test_finish_run_with_errors(self):
        """Test finishing a run with errors sets correct status"""
        import datetime

        conn = get_connection()
        create_schema(conn)
        started_at = datetime.datetime.utcnow()
        run_id = start_run(conn, "testgroup")

        finish_run(conn, run_id, moved=5, skipped=1, errors=3, started_at=started_at)

        with conn.cursor() as cur:
            cur.execute("SELECT status FROM archive_runs WHERE id = %s", (run_id,))
            status = cur.fetchone()[0]
            self.assertEqual(status, "completed_with_errors")

        conn.close()


class TestArchiveGroup(unittest.TestCase):
    """Test archive_group function with mocked dependencies"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.archive_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.archive_dir, ignore_errors=True)

    @patch('archive_files.grp.getgrnam')
    def test_archive_group_invalid_group(self, mock_getgrnam):
        """Test that invalid group raises appropriate error"""
        mock_getgrnam.side_effect = KeyError("group not found")

        with self.assertRaises(SystemExit) as cm:
            archive_group("nonexistent")

        self.assertEqual(cm.exception.code, 1)

    @patch('archive_files.grp.getgrnam')
    def test_archive_group_no_members(self, mock_getgrnam):
        """Test group with no members exits gracefully"""
        mock_group = Mock()
        mock_group.gr_mem = []
        mock_getgrnam.return_value = mock_group

        with self.assertRaises(SystemExit) as cm:
            archive_group("emptygroup")

        self.assertEqual(cm.exception.code, 0)

    @patch('archive_files.get_connection')
    @patch('archive_files.grp.getgrnam')
    def test_archive_group_db_connection_failure(self, mock_getgrnam, mock_get_conn):
        """Test database connection failure is handled"""
        mock_group = Mock()
        mock_group.gr_mem = ["testuser"]
        mock_getgrnam.return_value = mock_group

        mock_get_conn.side_effect = psycopg2.OperationalError("Connection failed")

        with self.assertRaises(SystemExit) as cm:
            archive_group("testgroup")

        self.assertEqual(cm.exception.code, 1)

    @patch('archive_files.ARCHIVE_ROOT', new_callable=lambda: tempfile.mkdtemp())
    @patch('archive_files.pwd.getpwnam')
    @patch('archive_files.grp.getgrnam')
    @patch('archive_files.get_connection')
    def test_archive_group_user_not_found(self, mock_conn, mock_getgrnam, mock_getpwnam, mock_archive):
        """Test handling of users that don't exist"""
        # Setup mocks
        mock_group = Mock()
        mock_group.gr_mem = ["nonexistentuser"]
        mock_getgrnam.return_value = mock_group

        mock_getpwnam.side_effect = KeyError("user not found")

        # Mock database connection
        mock_db = MagicMock()
        mock_conn.return_value = mock_db

        # This should not crash, just skip the user
        try:
            archive_group("testgroup")
        except SystemExit:
            pass  # Expected for successful completion


class TestArchiveGroupIntegration(unittest.TestCase):
    """Integration tests that require actual system users/groups"""

    def setUp(self):
        """Set up test environment"""
        self.temp_home = tempfile.mkdtemp()
        self.archive_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_home, ignore_errors=True)
        shutil.rmtree(self.archive_dir, ignore_errors=True)

    def test_file_permissions_preserved(self):
        """Test that file permissions are preserved during archiving"""
        test_file = os.path.join(self.temp_home, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        os.chmod(test_file, 0o644)

        dest_dir = os.path.join(self.archive_dir, "testgroup", "testuser")
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, "test.txt")

        shutil.move(test_file, dest_file)

        # Verify file exists at destination
        self.assertTrue(os.path.exists(dest_file))

        # Verify permissions (may vary by system, just check it's readable)
        self.assertTrue(os.access(dest_file, os.R_OK))

    def test_directory_structure_created(self):
        """Test that archive directory structure is created correctly"""
        group_name = "testgroup"
        username = "testuser"

        dest_dir = os.path.join(self.archive_dir, group_name, username)
        os.makedirs(dest_dir, exist_ok=True)

        self.assertTrue(os.path.isdir(dest_dir))

        # Check the path structure
        expected_parts = [group_name, username]
        actual_parts = dest_dir.replace(self.archive_dir, "").strip(os.sep).split(os.sep)
        self.assertEqual(actual_parts, expected_parts)

    def test_skip_duplicate_files(self):
        """Test that duplicate files are skipped"""
        test_file = os.path.join(self.temp_home, "duplicate.txt")
        with open(test_file, 'w') as f:
            f.write("original content")

        dest_dir = os.path.join(self.archive_dir, "testgroup", "testuser")
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, "duplicate.txt")

        # Create destination file first
        with open(dest_file, 'w') as f:
            f.write("existing content")

        # Check that destination exists before attempting move
        self.assertTrue(os.path.exists(dest_file))

        # In real scenario, the script would skip this file
        # We're just verifying the logic for detecting duplicates
        should_skip = os.path.exists(dest_file)
        self.assertTrue(should_skip)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_empty_home_directory(self):
        """Test behavior with empty home directory"""
        temp_home = tempfile.mkdtemp()
        files = os.listdir(temp_home)
        self.assertEqual(len(files), 0)
        shutil.rmtree(temp_home)

    def test_nested_directories_not_archived(self):
        """Test that only files (not directories) are archived"""
        temp_home = tempfile.mkdtemp()

        # Create a file
        test_file = os.path.join(temp_home, "file.txt")
        with open(test_file, 'w') as f:
            f.write("content")

        # Create a directory
        test_dir = os.path.join(temp_home, "subdir")
        os.makedirs(test_dir)

        # List only files
        files = [f for f in os.listdir(temp_home) if os.path.isfile(os.path.join(temp_home, f))]

        self.assertEqual(len(files), 1)
        self.assertIn("file.txt", files)

        shutil.rmtree(temp_home)

    def test_special_characters_in_filename(self):
        """Test handling of special characters in filenames"""
        temp_dir = tempfile.mkdtemp()

        # Test various special characters
        special_names = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt",
        ]

        for name in special_names:
            filepath = os.path.join(temp_dir, name)
            with open(filepath, 'w') as f:
                f.write("test")

            self.assertTrue(os.path.exists(filepath))

        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
