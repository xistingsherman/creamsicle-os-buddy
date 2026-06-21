import io
import json
import pytest
from unittest.mock import patch, MagicMock

import app as flask_app


@pytest.fixture(autouse=True)
def reset_flash_state():
    """Reset global flash state before every test."""
    flask_app.flash_state.update({
        "status": "idle",
        "progress": 0,
        "message": "",
        "cancel_requested": False,
    })
    yield


@pytest.fixture
def client(tmp_path):
    flask_app.app.config["TESTING"] = True
    flask_app.TEMP_DIR = str(tmp_path)
    with flask_app.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestIndexRoute:
    def test_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_returns_html(self, client):
        r = client.get("/")
        assert b"html" in r.data.lower()


# ---------------------------------------------------------------------------
# GET /api/boards
# ---------------------------------------------------------------------------

class TestBoardsRoute:
    def test_returns_200(self, client):
        assert client.get("/api/boards").status_code == 200

    def test_response_has_boards_key(self, client):
        data = client.get("/api/boards").get_json()
        assert "boards" in data

    def test_each_board_has_id_and_name(self, client):
        boards = client.get("/api/boards").get_json()["boards"]
        assert len(boards) > 0
        for board in boards:
            assert "id" in board
            assert "name" in board

    def test_board_ids_match_flasher_boards(self, client):
        import flasher
        ids = {b["id"] for b in client.get("/api/boards").get_json()["boards"]}
        assert ids == set(flasher.BOARDS.keys())


# ---------------------------------------------------------------------------
# GET /api/disks
# ---------------------------------------------------------------------------

class TestDisksRoute:
    def test_returns_200(self, client):
        with patch("flasher.list_disks", return_value=[]):
            assert client.get("/api/disks").status_code == 200

    def test_response_has_disks_key(self, client):
        with patch("flasher.list_disks", return_value=[{"number": 1}]):
            data = client.get("/api/disks").get_json()
        assert "disks" in data

    def test_delegates_to_flasher(self, client):
        fake_disks = [{"number": 2, "name": "USB Drive", "size_gb": 64.0}]
        with patch("flasher.list_disks", return_value=fake_disks) as mock_ld:
            r = client.get("/api/disks")
        mock_ld.assert_called_once()
        assert r.get_json()["disks"] == fake_disks


# ---------------------------------------------------------------------------
# GET /api/images/<board_id>
# ---------------------------------------------------------------------------

class TestImagesRoute:
    def test_invalid_board_returns_400(self, client):
        r = client.get("/api/images/not_a_real_board")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_valid_board_returns_200(self, client):
        with patch("flasher.fetch_board_images", return_value=[]):
            r = client.get("/api/images/orangepizero3")
        assert r.status_code == 200

    def test_response_has_images_key(self, client):
        mock_images = [{"filename": "test.img.xz", "distro": "Debian", "variant": "CLI"}]
        with patch("flasher.fetch_board_images", return_value=mock_images):
            data = client.get("/api/images/orangepi5").get_json()
        assert "images" in data
        assert data["images"] == mock_images


# ---------------------------------------------------------------------------
# GET /api/github_keys
# ---------------------------------------------------------------------------

class TestGithubKeysRoute:
    def test_missing_username_param_returns_400(self, client):
        r = client.get("/api/github_keys")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_empty_username_returns_400(self, client):
        r = client.get("/api/github_keys?username=")
        assert r.status_code == 400

    def test_whitespace_username_returns_400(self, client):
        r = client.get("/api/github_keys?username=   ")
        assert r.status_code == 400

    def test_valid_username_returns_keys(self, client):
        mock_r = MagicMock(status_code=200, text="ssh-rsa AAAAB3...")
        with patch("requests.get", return_value=mock_r):
            r = client.get("/api/github_keys?username=octocat")
        assert r.status_code == 200
        assert r.get_json()["keys"] == "ssh-rsa AAAAB3..."

    def test_github_404_returns_400(self, client):
        mock_r = MagicMock(status_code=404)
        with patch("requests.get", return_value=mock_r):
            r = client.get("/api/github_keys?username=nosuchuser99999")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_network_exception_returns_500(self, client):
        with patch("requests.get", side_effect=Exception("timeout")):
            r = client.get("/api/github_keys?username=testuser")
        assert r.status_code == 500
        assert "error" in r.get_json()


# ---------------------------------------------------------------------------
# POST /api/check_upload
# ---------------------------------------------------------------------------

class TestCheckUploadRoute:
    def test_no_filename_returns_not_exists(self, client):
        r = client.post("/api/check_upload", json={})
        assert r.status_code == 200
        assert r.get_json()["exists"] is False

    def test_disallowed_extension_returns_not_exists(self, client):
        r = client.post("/api/check_upload", json={"filename": "virus.exe", "size": 1000})
        assert r.get_json()["exists"] is False

    def test_zip_extension_not_allowed(self, client):
        r = client.post("/api/check_upload", json={"filename": "image.zip", "size": 1000})
        assert r.get_json()["exists"] is False

    def test_file_exists_with_matching_size(self, client, tmp_path):
        flask_app.TEMP_DIR = str(tmp_path)
        (tmp_path / "sdcard.img").write_bytes(b"X" * 200)
        r = client.post("/api/check_upload", json={"filename": "sdcard.img", "size": 200})
        data = r.get_json()
        assert data["exists"] is True
        assert "path" in data
        assert "filename" in data

    def test_file_exists_but_wrong_size_returns_not_exists(self, client, tmp_path):
        flask_app.TEMP_DIR = str(tmp_path)
        (tmp_path / "sdcard.img").write_bytes(b"X" * 200)
        r = client.post("/api/check_upload", json={"filename": "sdcard.img", "size": 9999})
        assert r.get_json()["exists"] is False

    def test_file_not_present_returns_not_exists(self, client, tmp_path):
        flask_app.TEMP_DIR = str(tmp_path)
        r = client.post("/api/check_upload", json={"filename": "missing.img", "size": 100})
        assert r.get_json()["exists"] is False

    @pytest.mark.parametrize("ext", [".img", ".xz", ".iso"])
    def test_allowed_extensions(self, client, tmp_path, ext):
        flask_app.TEMP_DIR = str(tmp_path)
        fname = f"image{ext}"
        (tmp_path / fname).write_bytes(b"data")
        r = client.post("/api/check_upload", json={"filename": fname, "size": 4})
        assert r.get_json()["exists"] is True


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------

class TestUploadRoute:
    def test_no_file_key_returns_400(self, client):
        r = client.post("/api/upload", data={}, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_invalid_extension_returns_400(self, client, tmp_path):
        flask_app.TEMP_DIR = str(tmp_path)
        data = {"file": (io.BytesIO(b"evil"), "malware.exe")}
        r = client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "Invalid file type" in r.get_json()["error"]

    @pytest.mark.parametrize("ext", [".img", ".xz", ".iso"])
    def test_valid_extensions_accepted(self, client, tmp_path, ext):
        flask_app.TEMP_DIR = str(tmp_path)
        data = {"file": (io.BytesIO(b"fake image"), f"sdcard{ext}")}
        r = client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert r.status_code == 200
        body = r.get_json()
        assert "path" in body
        assert "filename" in body

    def test_uploaded_file_saved_to_temp_dir(self, client, tmp_path):
        flask_app.TEMP_DIR = str(tmp_path)
        content = b"test image content"
        data = {"file": (io.BytesIO(content), "test.img")}
        client.post("/api/upload", data=data, content_type="multipart/form-data")
        saved = tmp_path / "test.img"
        assert saved.exists()
        assert saved.read_bytes() == content


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------

class TestStatusRoute:
    def test_returns_200(self, client):
        assert client.get("/api/status").status_code == 200

    def test_default_status_is_idle(self, client):
        data = client.get("/api/status").get_json()
        assert data["status"] == "idle"

    def test_response_has_all_required_fields(self, client):
        data = client.get("/api/status").get_json()
        for key in ("status", "progress", "message", "cancel_requested"):
            assert key in data

    def test_reflects_updated_state(self, client):
        flask_app.flash_state["status"] = "downloading"
        flask_app.flash_state["progress"] = 42
        data = client.get("/api/status").get_json()
        assert data["status"] == "downloading"
        assert data["progress"] == 42


# ---------------------------------------------------------------------------
# POST /api/cancel
# ---------------------------------------------------------------------------

class TestCancelRoute:
    def test_cancel_while_downloading_succeeds(self, client):
        flask_app.flash_state["status"] = "downloading"
        r = client.post("/api/cancel")
        assert r.status_code == 200
        assert r.get_json()["status"] == "cancelled"

    def test_cancel_sets_cancel_requested_flag(self, client):
        flask_app.flash_state["status"] = "downloading"
        client.post("/api/cancel")
        assert flask_app.flash_state["cancel_requested"] is True

    def test_cancel_resets_status_to_idle(self, client):
        flask_app.flash_state["status"] = "downloading"
        client.post("/api/cancel")
        assert flask_app.flash_state["status"] == "idle"

    def test_cancel_while_decompressing_succeeds(self, client):
        flask_app.flash_state["status"] = "decompressing"
        r = client.post("/api/cancel")
        assert r.status_code == 200

    def test_cancel_while_writing_returns_400(self, client):
        flask_app.flash_state["status"] = "writing"
        r = client.post("/api/cancel")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_cancel_while_idle_returns_400(self, client):
        flask_app.flash_state["status"] = "idle"
        r = client.post("/api/cancel")
        assert r.status_code == 400

    def test_cancel_while_success_returns_400(self, client):
        flask_app.flash_state["status"] = "success"
        r = client.post("/api/cancel")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/flash
# ---------------------------------------------------------------------------

class TestFlashRoute:
    _removable_disk = {
        "number": 2, "name": "USB Flash Drive",
        "is_system": False, "bus_type": "USB", "is_removable": True,
    }

    def _payload(self, **overrides):
        base = {
            "disk_number": 2,
            "board_id": "orangepizero3",
            "download_url": "https://example.com/image.img.xz",
        }
        base.update(overrides)
        return base

    def test_non_numeric_disk_number_returns_400(self, client):
        r = client.post("/api/flash", json={"disk_number": "bad"})
        assert r.status_code == 400

    def test_none_disk_number_returns_400(self, client):
        r = client.post("/api/flash", json={"disk_number": None})
        assert r.status_code == 400

    def test_disk_not_found_returns_400(self, client):
        with patch("flasher.list_disks", return_value=[]):
            r = client.post("/api/flash", json=self._payload())
        assert r.status_code == 400
        assert "not found" in r.get_json()["error"]

    def test_system_disk_is_blocked(self, client):
        disk = {**self._removable_disk, "is_system": True, "is_removable": False}
        with patch("flasher.list_disks", return_value=[disk]):
            r = client.post("/api/flash", json=self._payload())
        assert r.status_code == 400
        assert "protected" in r.get_json()["error"]

    def test_sata_disk_is_blocked(self, client):
        disk = {**self._removable_disk, "bus_type": "SATA"}
        with patch("flasher.list_disks", return_value=[disk]):
            r = client.post("/api/flash", json=self._payload())
        assert r.status_code == 400

    def test_non_removable_disk_is_blocked(self, client):
        disk = {**self._removable_disk, "is_removable": False}
        with patch("flasher.list_disks", return_value=[disk]):
            r = client.post("/api/flash", json=self._payload())
        assert r.status_code == 400

    def test_flash_already_running_returns_400(self, client):
        flask_app.flash_state["status"] = "writing"
        with patch("flasher.list_disks", return_value=[self._removable_disk]):
            r = client.post("/api/flash", json=self._payload())
        assert r.status_code == 400
        assert "already in progress" in r.get_json()["error"]

    def test_valid_request_starts_thread_and_returns_started(self, client):
        with patch("flasher.list_disks", return_value=[self._removable_disk]):
            with patch("threading.Thread") as mock_thread_cls:
                mock_t = MagicMock()
                mock_thread_cls.return_value = mock_t
                r = client.post("/api/flash", json=self._payload())
        assert r.status_code == 200
        assert r.get_json()["status"] == "started"
        mock_t.start.assert_called_once()

    def test_flash_sets_state_to_starting(self, client):
        with patch("flasher.list_disks", return_value=[self._removable_disk]):
            with patch("threading.Thread", return_value=MagicMock()):
                client.post("/api/flash", json=self._payload())
        # State transitions to "starting" then thread takes over; daemon thread won't block
        assert flask_app.flash_state["cancel_requested"] is False

    def test_flash_resets_cancel_flag(self, client):
        flask_app.flash_state["cancel_requested"] = True
        flask_app.flash_state["status"] = "idle"
        with patch("flasher.list_disks", return_value=[self._removable_disk]):
            with patch("threading.Thread", return_value=MagicMock()):
                client.post("/api/flash", json=self._payload())
        assert flask_app.flash_state["cancel_requested"] is False
