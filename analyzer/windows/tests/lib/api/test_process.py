import os
import threading
import unittest
from unittest.mock import MagicMock, patch

from lib.api.process import Process


class ProcessTests(unittest.TestCase):
    @patch("lib.api.process.PSAPI", MagicMock(), create=True)
    def test_unknown_image_name(self):
        process = Process()
        assert f"{process}" == "<Process 0 ???>"

    def test_known_image_name(self):
        mock_image_name = MagicMock()
        mock_image_name.return_value = self.id()
        with patch("lib.api.process.Process.get_image_name", mock_image_name):
            process = Process()
            assert f"{process}" == f"<Process 0 {self.id()}>"

    def test_process_self(self):
        _ = Process(pid=os.getpid(), thread_id=threading.get_ident())

    def test_process_fill_system_info(self):
        p = Process()
        p.fill_system_info()
        # arbitrary sysinfo field assertion here
        self.assertNotEqual(0, p.system_info.dwPageSize)

    @patch("lib.api.process.create_custom_folders")
    @patch("lib.api.process.os.access", return_value=True)
    def test_execute_expands_env_vars_in_execution_directory(self, _mock_access, mock_create_folders):
        p = Process(options={"executiondir": "%UserProfile%\\Desktop", "explorer_parent": "0"})
        with (
            patch.dict(os.environ, {"UserProfile": "C:\\Users\\Bruno"}, clear=False),
            patch("lib.api.process.KERNEL32") as mock_k32,
        ):
            mock_k32.CreateProcessW.return_value = True
            self.assertTrue(p.execute("C:\\Users\\Bruno\\Desktop\\sample.exe"))
            expected_dir = os.path.expandvars("%UserProfile%\\Desktop")
            mock_create_folders.assert_called_once_with(expected_dir)
            self.assertEqual(mock_k32.CreateProcessW.call_args[0][7], expected_dir)

    @patch("lib.api.process.create_custom_folders")
    @patch("lib.api.process.os.access", return_value=True)
    def test_execute_explorer_parent_passes_own_token(self, _mock_access, _mock_create_folders):
        """Default launch: explorer parent attribute AND an explicit duplicate of the analyzer token, so the
        sample does not inherit explorer's non-elevated token."""
        from lib.common.defines import CREATE_NEW_CONSOLE, CREATE_SUSPENDED, EXTENDED_STARTUPINFO_PRESENT

        token = MagicMock(name="token")
        p = Process(options={"executiondir": "C:\\Users\\Bruno\\Desktop"})
        with (
            patch.object(p, "duplicate_own_primary_token", return_value=token),
            patch.object(p, "build_parent_attribute_list", return_value=(None, MagicMock(), None)) as mock_build,
            patch.object(p, "is_elevated", return_value=True),
            patch("lib.api.process.ADVAPI32") as mock_adv,
            patch("lib.api.process.KERNEL32") as mock_k32,
        ):
            mock_adv.CreateProcessAsUserW.return_value = True
            self.assertTrue(p.execute("C:\\Users\\Bruno\\Desktop\\installer.exe"))
            mock_build.assert_called_once()
            args = mock_adv.CreateProcessAsUserW.call_args[0]
            self.assertIs(args[0], token)
            self.assertEqual(args[6], CREATE_NEW_CONSOLE | EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED)
            mock_k32.CreateProcessW.assert_not_called()

    @patch("lib.api.process.get_error_string", return_value="The requested operation requires elevation.")
    @patch("lib.api.process.create_custom_folders")
    @patch("lib.api.process.os.access", return_value=True)
    def test_execute_fallback_when_parent_spoofing_fails(self, _mock_access, _mock_create_folders, _mock_err_str):
        from lib.common.defines import CREATE_NEW_CONSOLE, CREATE_SUSPENDED

        p = Process(options={"executiondir": "C:\\Users\\Bruno\\Desktop"})
        with (
            patch.object(p, "duplicate_own_primary_token", return_value=MagicMock()),
            patch.object(p, "build_parent_attribute_list", return_value=(None, MagicMock(), None)),
            patch.object(p, "is_elevated", return_value=True),
            patch("lib.api.process.ADVAPI32") as mock_adv,
            patch("lib.api.process.KERNEL32") as mock_k32,
        ):
            mock_adv.CreateProcessAsUserW.return_value = False
            mock_k32.CreateProcessW.return_value = True
            mock_k32.GetLastError.return_value = 740
            self.assertTrue(p.execute("C:\\Users\\Bruno\\Desktop\\installer.exe"))
            self.assertEqual(mock_k32.CreateProcessW.call_count, 1)
            self.assertEqual(mock_k32.CreateProcessW.call_args[0][5], CREATE_NEW_CONSOLE | CREATE_SUSPENDED)

    @patch("lib.api.process.get_error_string", return_value="Access is denied.")
    @patch("lib.api.process.create_custom_folders")
    @patch("lib.api.process.os.access", return_value=True)
    def test_execute_returns_false_when_both_attempts_fail(self, _mock_access, _mock_create_folders, _mock_err_str):
        p = Process(options={"executiondir": "C:\\Users\\Bruno\\Desktop"})
        with (
            patch.object(p, "duplicate_own_primary_token", return_value=MagicMock()),
            patch.object(p, "build_parent_attribute_list", return_value=(None, MagicMock(), None)),
            patch("lib.api.process.ADVAPI32") as mock_adv,
            patch("lib.api.process.KERNEL32") as mock_k32,
        ):
            mock_adv.CreateProcessAsUserW.return_value = False
            mock_k32.CreateProcessW.return_value = False
            mock_k32.GetLastError.return_value = 5
            self.assertFalse(p.execute("C:\\Users\\Bruno\\Desktop\\installer.exe"))
            self.assertEqual(mock_adv.CreateProcessAsUserW.call_count, 1)
            self.assertEqual(mock_k32.CreateProcessW.call_count, 1)

    @patch("lib.api.process.create_custom_folders")
    @patch("lib.api.process.os.access", return_value=True)
    def test_execute_no_parent_when_token_duplication_fails(self, _mock_access, _mock_create_folders):
        """Never launch with the explorer parent attribute without an explicit token."""
        from lib.common.defines import CREATE_NEW_CONSOLE, CREATE_SUSPENDED

        p = Process(options={"executiondir": "C:\\Users\\Bruno\\Desktop"})
        with (
            patch.object(p, "duplicate_own_primary_token", return_value=None),
            patch.object(p, "build_parent_attribute_list") as mock_build,
            patch.object(p, "is_elevated", return_value=True),
            patch("lib.api.process.ADVAPI32") as mock_adv,
            patch("lib.api.process.KERNEL32") as mock_k32,
        ):
            mock_k32.CreateProcessW.return_value = True
            self.assertTrue(p.execute("C:\\Users\\Bruno\\Desktop\\installer.exe"))
            mock_build.assert_not_called()
            mock_adv.CreateProcessAsUserW.assert_not_called()
            self.assertEqual(mock_k32.CreateProcessW.call_args[0][5], CREATE_NEW_CONSOLE | CREATE_SUSPENDED)

    @patch("lib.api.process.create_custom_folders")
    @patch("lib.api.process.os.access", return_value=True)
    def test_execute_explorer_parent_disabled(self, _mock_access, _mock_create_folders):
        from lib.common.defines import CREATE_NEW_CONSOLE, CREATE_SUSPENDED

        p = Process(options={"executiondir": "C:\\Users\\Bruno\\Desktop", "explorer_parent": "0"})
        with (
            patch.object(p, "duplicate_own_primary_token") as mock_dup,
            patch.object(p, "build_parent_attribute_list") as mock_build,
            patch.object(p, "is_elevated", return_value=True),
            patch("lib.api.process.KERNEL32") as mock_k32,
        ):
            mock_k32.CreateProcessW.return_value = True
            self.assertTrue(p.execute("C:\\Users\\Bruno\\Desktop\\installer.exe"))
            mock_dup.assert_not_called()
            mock_build.assert_not_called()
            self.assertEqual(mock_k32.CreateProcessW.call_args[0][5], CREATE_NEW_CONSOLE | CREATE_SUSPENDED)

    def test_build_parent_attribute_list_annotation_not_evaluated(self):
        """ctypes.Array[...] raises TypeError at import time on Python 3.8 (Windows 7 guests) unless quoted."""
        self.assertIsInstance(Process.build_parent_attribute_list.__annotations__["return"], str)
