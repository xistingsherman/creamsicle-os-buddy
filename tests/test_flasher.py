import io
import json
import lzma
import pytest
from unittest.mock import patch, MagicMock

import flasher


# ---------------------------------------------------------------------------
# BOARDS constant
# ---------------------------------------------------------------------------

class TestBoards:
    def test_contains_all_expected_board_ids(self):
        expected = [
            "orangepizero3", "orangepi5", "orangepi5-plus", "orangepizero2",
            "orangepi3-lts", "orangepi4-lts", "orangepi4pro",
            "orangepione", "orangepizero", "orangepipc2",
        ]
        for board_id in expected:
            assert board_id in flasher.BOARDS, f"Missing board: {board_id}"

    def test_board_names_are_non_empty_strings(self):
        for board_id, name in flasher.BOARDS.items():
            assert isinstance(name, str) and name, f"Board '{board_id}' has empty name"


# ---------------------------------------------------------------------------
# list_disks
# ---------------------------------------------------------------------------

class TestListDisks:
    def _mock_runs(self, boot_num, disks_data):
        boot_result = MagicMock()
        boot_result.stdout = str(boot_num) + "\n"

        disks_result = MagicMock()
        disks_result.stdout = json.dumps(disks_data)

        return [boot_result, disks_result]

    def test_returns_empty_list_when_powershell_fails(self):
        with patch("subprocess.run", side_effect=Exception("no powershell")):
            result = flasher.list_disks()
        assert result == []

    def test_returns_empty_list_on_empty_disk_output(self):
        boot_result = MagicMock()
        boot_result.stdout = "0\n"
        disks_result = MagicMock()
        disks_result.stdout = ""
        with patch("subprocess.run", side_effect=[boot_result, disks_result]):
            result = flasher.list_disks()
        assert result == []

    def test_marks_boot_disk_as_system(self):
        side_effects = self._mock_runs(0, [
            {"Number": 0, "FriendlyName": "Samsung SSD", "Size": 512 * 1024**3, "BusType": "NVMe"},
        ])
        with patch("subprocess.run", side_effect=side_effects):
            result = flasher.list_disks()
        assert result[0]["is_system"] is True
        assert result[0]["is_removable"] is False

    def test_usb_non_system_disk_is_removable(self):
        side_effects = self._mock_runs(0, [
            {"Number": 0, "FriendlyName": "Sys Drive", "Size": 512 * 1024**3, "BusType": "NVMe"},
            {"Number": 1, "FriendlyName": "USB Flash", "Size": 32 * 1024**3, "BusType": "USB"},
        ])
        with patch("subprocess.run", side_effect=side_effects):
            result = flasher.list_disks()
        usb = next(d for d in result if d["number"] == 1)
        assert usb["is_removable"] is True
        assert usb["is_system"] is False

    def test_sata_non_system_disk_is_not_removable(self):
        side_effects = self._mock_runs(0, [
            {"Number": 1, "FriendlyName": "SATA HDD", "Size": 1000 * 1024**3, "BusType": "SATA"},
        ])
        with patch("subprocess.run", side_effect=side_effects):
            result = flasher.list_disks()
        assert result[0]["is_removable"] is False

    def test_single_disk_dict_handled(self):
        """PowerShell may return a single object dict instead of a list."""
        side_effects = self._mock_runs(0,
            {"Number": 0, "FriendlyName": "Only Drive", "Size": 256 * 1024**3, "BusType": "NVMe"}
        )
        with patch("subprocess.run", side_effect=side_effects):
            result = flasher.list_disks()
        assert isinstance(result, list) and len(result) == 1

    def test_size_converted_to_gb(self):
        size_bytes = 64 * 1024**3
        side_effects = self._mock_runs(0, [
            {"Number": 1, "FriendlyName": "SD Card", "Size": size_bytes, "BusType": "USB"},
        ])
        with patch("subprocess.run", side_effect=side_effects):
            result = flasher.list_disks()
        assert result[0]["size_gb"] == 64.0

    def test_results_are_reversed(self):
        side_effects = self._mock_runs(0, [
            {"Number": 0, "FriendlyName": "Drive A", "Size": 100 * 1024**3, "BusType": "NVMe"},
            {"Number": 1, "FriendlyName": "Drive B", "Size": 32 * 1024**3, "BusType": "USB"},
        ])
        with patch("subprocess.run", side_effect=side_effects):
            result = flasher.list_disks()
        # After reverse: disk 1 first, disk 0 last
        assert result[0]["number"] == 1
        assert result[1]["number"] == 0


# ---------------------------------------------------------------------------
# fetch_board_images
# ---------------------------------------------------------------------------

class TestFetchBoardImages:
    def _mock_response(self, status_code=200, html=""):
        r = MagicMock()
        r.status_code = status_code
        r.text = html
        return r

    def test_returns_empty_list_on_network_error(self):
        with patch("requests.get", side_effect=Exception("Connection refused")):
            result = flasher.fetch_board_images("orangepizero3")
        assert result == []

    def test_returns_empty_list_on_non_200_status(self):
        with patch("requests.get", return_value=self._mock_response(404)):
            result = flasher.fetch_board_images("orangepizero3")
        assert result == []

    def test_parses_img_xz_links(self):
        html = '<a href="Armbian_25.5_Orangepizero3_bookworm_current_6.12.23_minimal.img.xz">f</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert len(result) == 1
        assert result[0]["filename"].endswith(".img.xz")

    def test_ignores_asc_and_sha_files(self):
        html = "\n".join([
            '<a href="file.img.xz.asc">asc</a>',
            '<a href="file.img.xz.sha">sha</a>',
            '<a href="Armbian_bookworm_current_6.12.23.img.xz">ok</a>',
        ])
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert len(result) == 1

    def test_ignores_non_xz_files(self):
        html = '<a href="readme.txt">txt</a><a href="Armbian_bookworm_current_6.img.xz">ok</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert len(result) == 1

    @pytest.mark.parametrize("keyword,expected_distro", [
        ("bookworm", "Debian Bookworm"),
        ("trixie", "Debian Trixie"),
        ("bullseye", "Debian Bullseye"),
        ("noble", "Ubuntu Noble"),
        ("jammy", "Ubuntu Jammy"),
        ("resolute", "Ubuntu Resolute"),
    ])
    def test_detects_distro(self, keyword, expected_distro):
        html = f'<a href="Armbian_{keyword}_current_6.12.img.xz">f</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert result[0]["distro"] == expected_distro

    @pytest.mark.parametrize("keyword,expected_variant", [
        ("xfce_desktop", "Desktop (XFCE)"),
        ("gnome_desktop", "Desktop (Gnome)"),
        ("kde_desktop", "Desktop (KDE Plasma)"),
        ("cinnamon_desktop", "Desktop (Cinnamon)"),
        ("minimal", "Minimal / CLI"),
    ])
    def test_detects_variant(self, keyword, expected_variant):
        html = f'<a href="Armbian_bookworm_{keyword}_current_6.12.img.xz">f</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert result[0]["variant"] == expected_variant

    @pytest.mark.parametrize("kernel_tag", ["current", "vendor", "edge"])
    def test_parses_kernel_version(self, kernel_tag):
        html = f'<a href="Armbian_bookworm_{kernel_tag}_6.12.23_minimal.img.xz">f</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert result[0]["kernel"] == "Kernel 6.12.23"

    def test_download_url_contains_board_and_filename(self):
        board_id = "orangepizero3"
        filename = "Armbian_bookworm_current_6.12.23_minimal.img.xz"
        html = f'<a href="{filename}">f</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images(board_id)
        assert board_id in result[0]["download_url"]
        assert filename in result[0]["download_url"]

    def test_unknown_distro_returns_unknown(self):
        html = '<a href="Armbian_unknowndistro_current_6.12.img.xz">f</a>'
        with patch("requests.get", return_value=self._mock_response(html=html)):
            result = flasher.fetch_board_images("orangepizero3")
        assert result[0]["distro"] == "Unknown"


# ---------------------------------------------------------------------------
# decompress_xz
# ---------------------------------------------------------------------------

class TestDecompressXz:
    def test_decompresses_correctly(self, tmp_path):
        original = b"Hello, Orange Pi! " * 500
        xz_path = tmp_path / "test.img.xz"
        img_path = tmp_path / "test.img"

        with lzma.open(str(xz_path), "wb") as f:
            f.write(original)

        flasher.decompress_xz(str(xz_path), str(img_path))

        assert img_path.exists()
        assert img_path.read_bytes() == original

    def test_progress_callback_is_called(self, tmp_path):
        data = b"X" * (2 * 1024 * 1024)
        xz_path = tmp_path / "test.img.xz"
        img_path = tmp_path / "test.img"
        with lzma.open(str(xz_path), "wb") as f:
            f.write(data)

        calls = []
        flasher.decompress_xz(str(xz_path), str(img_path), lambda s, p: calls.append((s, p)))

        assert len(calls) > 0
        assert all(s == "decompressing" for s, _ in calls)

    def test_progress_values_are_0_to_100(self, tmp_path):
        data = b"Y" * (3 * 1024 * 1024)
        xz_path = tmp_path / "big.img.xz"
        img_path = tmp_path / "big.img"
        with lzma.open(str(xz_path), "wb") as f:
            f.write(data)

        values = []
        flasher.decompress_xz(str(xz_path), str(img_path), lambda s, p: values.append(p))

        assert all(0 <= p <= 100 for p in values)

    def test_works_without_progress_callback(self, tmp_path):
        data = b"Z" * 1024
        xz_path = tmp_path / "small.img.xz"
        img_path = tmp_path / "small.img"
        with lzma.open(str(xz_path), "wb") as f:
            f.write(data)

        flasher.decompress_xz(str(xz_path), str(img_path))
        assert img_path.read_bytes() == data


# ---------------------------------------------------------------------------
# _build_setup_script
# ---------------------------------------------------------------------------

class TestBuildSetupScript:
    def _build(self, **overrides):
        defaults = dict(
            hostname="", username="", password="",
            wifi_ssid="", wifi_password="", ssh_key=None,
            enable_ssh=False, preload_apps=None,
        )
        defaults.update(overrides)
        return flasher._build_setup_script(**defaults)

    def test_starts_with_bash_shebang(self):
        assert self._build().startswith("#!/bin/bash")

    def test_includes_set_e(self):
        assert "set -e" in self._build()

    def test_hostname_sets_etc_hostname(self):
        script = self._build(hostname="my-orangepi")
        assert "my-orangepi" in script
        assert "/etc/hostname" in script
        assert "/etc/hosts" in script

    def test_no_hostname_section_skipped(self):
        script = self._build(hostname="")
        assert "/etc/hostname" not in script

    def test_username_and_password_creates_user(self):
        script = self._build(username="alice", password="secret")
        assert "useradd" in script
        assert "alice" in script
        assert "alice:secret" in script

    def test_username_without_password_skips_user_creation(self):
        script = self._build(username="alice", password="")
        assert "useradd" not in script

    def test_ssh_key_written_to_authorized_keys(self):
        script = self._build(username="alice", ssh_key="ssh-rsa AAAAB3NzaC1yc2E test@host")
        assert "authorized_keys" in script
        assert "ssh-rsa AAAAB3NzaC1yc2E test@host" in script

    def test_ssh_key_requires_username(self):
        script = self._build(username="", ssh_key="ssh-rsa AAAA")
        assert "authorized_keys" not in script

    def test_enable_ssh_adds_systemctl(self):
        script = self._build(enable_ssh=True)
        assert "systemctl enable ssh" in script

    def test_disable_ssh_skips_systemctl(self):
        script = self._build(enable_ssh=False)
        assert "systemctl enable ssh" not in script

    def test_wifi_configured_with_nmcli(self):
        script = self._build(wifi_ssid="HomeNetwork", wifi_password="pass1234")
        assert "HomeNetwork" in script
        assert "pass1234" in script
        assert "nmcli" in script

    def test_no_wifi_skips_wifi_config(self):
        script = self._build(wifi_ssid="")
        assert "nmcli" not in script

    def test_firefox_install(self):
        script = self._build(preload_apps=["firefox"])
        assert "firefox" in script
        assert "apt-get install" in script

    def test_vscode_install(self):
        script = self._build(preload_apps=["vscode"])
        assert "packages.microsoft.com" in script
        assert "apt-get install -y code" in script

    def test_kiwix_install(self):
        script = self._build(preload_apps=["kiwix"])
        assert "kiwix" in script

    def test_dictionary_install(self):
        script = self._build(preload_apps=["dictionary"])
        assert "goldendict" in script

    def test_sudoku_install(self):
        script = self._build(preload_apps=["sudoku"])
        assert "gnome-sudoku" in script

    def test_stardew_uses_given_username_path(self):
        script = self._build(username="gamer", preload_apps=["stardew"])
        assert "/home/gamer/StardewValley" in script

    def test_stardew_falls_back_to_pi_user(self):
        script = self._build(username="", preload_apps=["stardew"])
        assert "/home/pi/StardewValley" in script

    def test_multiple_apps_all_installed(self):
        script = self._build(preload_apps=["firefox", "kiwix", "sudoku"])
        assert "firefox" in script
        assert "kiwix" in script
        assert "gnome-sudoku" in script

    def test_apt_update_included_when_apps_requested(self):
        script = self._build(preload_apps=["firefox"])
        assert "apt-get update" in script

    def test_ends_with_reboot(self):
        script = self._build(hostname="test")
        assert "reboot" in script

    def test_empty_call_produces_valid_bash_header(self):
        script = self._build()
        assert "#!/bin/bash" in script
        assert "set -e" in script
        assert "reboot" in script
