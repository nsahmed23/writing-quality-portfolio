"""Append-only artifact storage with explicit containment and SHA-256 receipts."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _FILE_READ_ATTRIBUTES = 0x0080
    _DELETE = 0x00010000
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_RENAME_INFO_CLASS = 3
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("file_attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial_number", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        ]

    class _FileRenameInformation(ctypes.Structure):
        _fields_ = [
            ("flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    _kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    _kernel32.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL


class ImmutableWriteError(FileExistsError):
    """Raised when an immutable artifact already exists."""


class PathSafetyError(ValueError):
    """Raised when an artifact path or filesystem alias escapes authorization."""


class TamperError(RuntimeError):
    """Raised when stored bytes do not match a receipt."""


@dataclass(frozen=True)
class Receipt:
    relative_path: str
    sha256: str
    byte_count: int


def _lexical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_alias(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _snapshot(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _path_components(path: Path) -> list[Path]:
    absolute = _lexical_absolute(path)
    current = Path(absolute.anchor)
    components = [current]
    for part in absolute.parts[1:]:
        current = current / part
        components.append(current)
    return components


def _lstat_no_alias(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PathSafetyError(f"{label} is unavailable: {path}") from exc
    if _is_alias(metadata):
        raise PathSafetyError(f"{label} contains a symlink, junction, or reparse point: {path}")
    return metadata


def _assert_existing_chain_has_no_aliases(path: Path, *, require_leaf: bool) -> os.stat_result | None:
    """Inspect lexical ancestors with lstat before any path resolution or I/O."""

    components = _path_components(path)
    leaf_metadata: os.stat_result | None = None
    for index, component in enumerate(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            if require_leaf:
                raise PathSafetyError(f"authorized path is missing: {component}")
            return None
        except OSError as exc:
            raise PathSafetyError(f"authorized path is unavailable: {component}") from exc
        if _is_alias(metadata):
            raise PathSafetyError(
                f"authorized path contains a symlink, junction, or reparse point: {component}"
            )
        if index < len(components) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise PathSafetyError(f"authorized path ancestor is not a directory: {component}")
        leaf_metadata = metadata
    return leaf_metadata


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    volume = metadata.st_dev
    if os.name == "nt":
        # GetFileInformationByHandle exposes the DWORD volume serial. Python
        # 3.13+ reports the same serial in a wider st_dev representation.
        volume &= 0xFFFFFFFF
    return volume, metadata.st_ino


if os.name == "nt":
    def _windows_handle_information(handle: int) -> _ByHandleFileInformation:
        information = _ByHandleFileInformation()
        if not _kernel32.GetFileInformationByHandle(handle, ctypes.byref(information)):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        return information


    def _windows_handle_identity(information: _ByHandleFileInformation) -> tuple[int, int]:
        file_index = (information.file_index_high << 32) | information.file_index_low
        return information.volume_serial_number, file_index


    def _open_windows_directory(path: Path, *, pin_rename: bool) -> tuple[int, tuple[int, int]]:
        desired_access = _FILE_READ_ATTRIBUTES | (_DELETE if pin_rename else 0)
        handle = _kernel32.CreateFileW(
            str(path),
            desired_access,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            raise PathSafetyError(f"directory boundary could not be held: {path}") from OSError(
                error,
                os.strerror(error),
            )
        try:
            information = _windows_handle_information(handle)
            if information.file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise PathSafetyError(
                    f"directory boundary contains a symlink, junction, or reparse point: {path}"
                )
            if not information.file_attributes & _FILE_ATTRIBUTE_DIRECTORY:
                raise PathSafetyError(f"directory boundary component is not a directory: {path}")
            return handle, _windows_handle_identity(information)
        except Exception:
            _kernel32.CloseHandle(handle)
            raise


    def _rename_windows_directory_handle(handle: int, destination: Path) -> None:
        encoded_name = str(destination).encode("utf-16-le")
        # Include an explicitly zeroed WCHAR after the counted name. Some
        # Windows filesystem drivers inspect the terminator even though the
        # contract supplies FileNameLength in bytes.
        buffer_size = ctypes.sizeof(_FileRenameInformation) + len(encoded_name) + 2
        buffer = ctypes.create_string_buffer(buffer_size)
        information = ctypes.cast(buffer, ctypes.POINTER(_FileRenameInformation)).contents
        information.flags = 0
        information.root_directory = None
        information.file_name_length = len(encoded_name)
        ctypes.memmove(
            ctypes.addressof(buffer) + _FileRenameInformation.file_name.offset,
            encoded_name,
            len(encoded_name),
        )
        if not _kernel32.SetFileInformationByHandle(
            handle,
            _FILE_RENAME_INFO_CLASS,
            buffer,
            buffer_size,
        ):
            error = ctypes.get_last_error()
            if error in {80, 183}:
                raise FileExistsError(error, os.strerror(error), str(destination))
            raise OSError(error, os.strerror(error), str(destination))


class _HeldDirectoryBoundary:
    """Hold a non-reparse lexical directory chain during path-based I/O.

    On Windows, the deepest requested directory is opened with DELETE access
    and without FILE_SHARE_DELETE. That prevents it, or an ancestor containing
    it, from being renamed while the guard is live. It intentionally does not
    claim to prevent child creation or deletion inside a held directory.
    """

    def __init__(self, authorized_root: str | Path) -> None:
        self.authorized_root = _lexical_absolute(authorized_root)
        self._entries: list[tuple[Path, tuple[int, int], int]] = []
        self._by_key: dict[str, tuple[Path, tuple[int, int], int]] = {}
        self._entered = False

    @staticmethod
    def _key(path: Path) -> str:
        return os.path.normcase(str(_lexical_absolute(path)))

    def _open_component(self, path: Path, *, pin_rename: bool) -> None:
        key = self._key(path)
        if key in self._by_key:
            return
        before = _lstat_no_alias(path, label="directory boundary")
        if not stat.S_ISDIR(before.st_mode):
            raise PathSafetyError(f"directory boundary component is not a directory: {path}")
        if os.name == "nt":
            descriptor, opened_identity = _open_windows_directory(path, pin_rename=pin_rename)
        else:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags)
            except OSError as exc:
                raise PathSafetyError(f"directory boundary could not be held: {path}") from exc
            opened = os.fstat(descriptor)
            opened_identity = _identity(opened)
        try:
            after = _lstat_no_alias(path, label="directory boundary")
            if opened_identity != _identity(before) or opened_identity != _identity(after):
                raise PathSafetyError(f"directory boundary changed while it was opened: {path}")
        except Exception:
            if os.name == "nt":
                _kernel32.CloseHandle(descriptor)
            else:
                os.close(descriptor)
            raise
        entry = (path, opened_identity, descriptor)
        self._entries.append(entry)
        self._by_key[key] = entry

    def __enter__(self) -> _HeldDirectoryBoundary:
        if self._entered:
            raise RuntimeError("directory boundary guard cannot be re-entered")
        self._entered = True
        try:
            components = _path_components(self.authorized_root)
            for index, component in enumerate(components):
                self._open_component(component, pin_rename=index == len(components) - 1)
            self.assert_current()
            return self
        except Exception:
            self.close()
            raise

    def ensure_directory(self, directory: str | Path, *, create: bool) -> Path:
        if not self._entered:
            raise RuntimeError("directory boundary guard is not active")
        target = _lexical_absolute(directory)
        try:
            relative = target.relative_to(self.authorized_root)
        except ValueError as exc:
            raise PathSafetyError("directory escapes the explicit authorized root") from exc
        current = self.authorized_root
        for part in relative.parts:
            current = current / part
            if self._key(current) in self._by_key:
                continue
            if create:
                try:
                    os.mkdir(current)
                except FileExistsError:
                    pass
            self._open_component(current, pin_rename=True)
        self.assert_current()
        return target

    def handle_for(self, directory: str | Path) -> int:
        try:
            return self._by_key[self._key(_lexical_absolute(directory))][2]
        except KeyError as exc:
            raise PathSafetyError("directory is not held by this boundary") from exc

    def release_descendants(self, directory: str | Path) -> None:
        """Release held descendants while retaining the directory itself."""

        ancestor = _lexical_absolute(directory)
        retained: list[tuple[Path, tuple[int, int], int]] = []
        for entry in self._entries:
            path, _identity_value, descriptor = entry
            try:
                suffix = path.relative_to(ancestor)
            except ValueError:
                retained.append(entry)
                continue
            if not suffix.parts:
                retained.append(entry)
                continue
            if os.name == "nt":
                _kernel32.CloseHandle(descriptor)
            else:
                os.close(descriptor)
        self._entries = retained
        self._by_key = {self._key(entry[0]): entry for entry in retained}
        self.assert_current()

    def assert_current(self) -> None:
        for path, expected_identity, descriptor in self._entries:
            current = _lstat_no_alias(path, label="held directory boundary")
            if _identity(current) != expected_identity:
                raise PathSafetyError(f"held directory boundary changed: {path}")
            if os.name == "nt":
                information = _windows_handle_information(descriptor)
                if information.file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise PathSafetyError(f"held directory became a reparse point: {path}")
                opened_identity = _windows_handle_identity(information)
            else:
                opened_identity = _identity(os.fstat(descriptor))
            if opened_identity != expected_identity:
                raise PathSafetyError(f"held directory handle changed: {path}")

    def rename_directory(self, source: str | Path, destination: str | Path) -> None:
        source_path = _lexical_absolute(source)
        destination_path = _lexical_absolute(destination)
        if destination_path.parent != source_path.parent:
            raise PathSafetyError("held directory publication must stay in one parent")
        self.ensure_directory(source_path, create=False)
        self.ensure_directory(destination_path.parent, create=False)
        try:
            destination_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"refusing to replace existing directory: {destination_path}")
        self.release_descendants(source_path)
        self.assert_current()
        if os.name == "nt":
            _rename_windows_directory_handle(self.handle_for(source_path), destination_path)
        else:
            os.rename(source_path, destination_path)
        remapped: list[tuple[Path, tuple[int, int], int]] = []
        for path, identity, descriptor in self._entries:
            try:
                suffix = path.relative_to(source_path)
            except ValueError:
                replacement = path
            else:
                replacement = destination_path / suffix
            remapped.append((replacement, identity, descriptor))
        self._entries = remapped
        self._by_key = {self._key(entry[0]): entry for entry in remapped}
        self.assert_current()

    def close(self) -> None:
        for _path, _identity_value, descriptor in reversed(self._entries):
            if os.name == "nt":
                _kernel32.CloseHandle(descriptor)
            else:
                os.close(descriptor)
        self._entries.clear()
        self._by_key.clear()
        self._entered = False

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False


_boundary_locks_guard = threading.Lock()
_boundary_locks: dict[str, threading.RLock] = {}
_active_boundaries = threading.local()


def _boundary_lock(key: str) -> threading.RLock:
    with _boundary_locks_guard:
        return _boundary_locks.setdefault(key, threading.RLock())


@contextmanager
def _hold_directory_tree(
    directory: str | Path,
    *,
    authorized_root: str | Path,
    create: bool,
) -> Iterator[_HeldDirectoryBoundary]:
    authorization = _lexical_absolute(authorized_root)
    key = os.path.normcase(str(authorization))
    lock = _boundary_lock(key)
    with lock:
        active = getattr(_active_boundaries, "values", None)
        if active is None:
            active = {}
            _active_boundaries.values = active
        existing = active.get(key)
        if existing is not None:
            existing.ensure_directory(directory, create=create)
            yield existing
            return
        with _HeldDirectoryBoundary(authorization) as boundary:
            active[key] = boundary
            try:
                boundary.ensure_directory(directory, create=create)
                yield boundary
            finally:
                active.pop(key, None)


class RawStore:
    """A filesystem store where each relative path may be published once.

    ``authorized_root`` is a required lexical trust boundary. Neither it nor any
    existing ancestor, store directory, target parent, or target may be a
    symlink, junction, or other reparse point.
    """

    def __init__(self, root: str | Path, *, authorized_root: str | Path) -> None:
        self.authorized_root = _lexical_absolute(authorized_root)
        self.root = _lexical_absolute(root)
        try:
            self.root.relative_to(self.authorized_root)
        except ValueError as exc:
            raise PathSafetyError("store root escapes its explicit authorized root") from exc

        authorized_metadata = _assert_existing_chain_has_no_aliases(
            self.authorized_root,
            require_leaf=True,
        )
        assert authorized_metadata is not None
        if not stat.S_ISDIR(authorized_metadata.st_mode):
            raise PathSafetyError("authorized root is not a directory")
        self._authorized_identity = _identity(authorized_metadata)
        with _hold_directory_tree(
            self.root,
            authorized_root=self.authorized_root,
            create=True,
        ):
            root_metadata = _lstat_no_alias(self.root, label="store root")
            if not stat.S_ISDIR(root_metadata.st_mode):
                raise PathSafetyError("store root is not a directory")
            self._root_identity = _identity(root_metadata)
        self._assert_store_identity()

    def _assert_store_identity(self) -> None:
        _assert_existing_chain_has_no_aliases(self.authorized_root, require_leaf=True)
        authorized = _lstat_no_alias(self.authorized_root, label="authorized root")
        if _identity(authorized) != self._authorized_identity:
            raise PathSafetyError("authorized root changed after store initialization")
        root = _lstat_no_alias(self.root, label="store root")
        if not stat.S_ISDIR(root.st_mode) or _identity(root) != self._root_identity:
            raise PathSafetyError("store root changed after store initialization")

    def _make_directories_safely(self, path: Path, *, base: Path) -> None:
        with _hold_directory_tree(path, authorized_root=base, create=True):
            pass

    def _target(self, relative_path: str) -> tuple[str, Path]:
        if not isinstance(relative_path, str) or not relative_path.strip() or "\x00" in relative_path:
            raise PathSafetyError("artifact path must be non-empty relative text")
        windows = PureWindowsPath(relative_path)
        posix = PurePosixPath(relative_path.replace("\\", "/"))
        if windows.is_absolute() or windows.drive or posix.is_absolute():
            raise PathSafetyError("absolute artifact paths are forbidden")
        parts = posix.parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise PathSafetyError("artifact path traversal is forbidden")
        reserved = {
            "con",
            "prn",
            "aux",
            "nul",
            *(f"com{i}" for i in range(1, 10)),
            *(f"lpt{i}" for i in range(1, 10)),
        }
        for part in parts:
            device_stem = part.split(".", 1)[0].casefold()
            if (
                ":" in part
                or part.endswith((" ", "."))
                or device_stem in reserved
                or any(ord(character) < 32 for character in part)
            ):
                raise PathSafetyError("artifact path contains a Windows-unsafe component")
        normalized = "/".join(parts)
        target = self.root.joinpath(*parts)
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PathSafetyError("artifact path escapes the store") from exc
        self._assert_store_identity()
        _assert_existing_chain_has_no_aliases(target, require_leaf=False)
        return normalized, target

    def _prepare_parent(self, target: Path) -> None:
        self._assert_store_identity()
        self._make_directories_safely(target.parent, base=self.root)
        _assert_existing_chain_has_no_aliases(target.parent, require_leaf=True)
        self._assert_store_identity()

    def _directory_path(self, path_or_relative: str | Path) -> Path:
        supplied = Path(path_or_relative)
        if supplied.is_absolute():
            directory = _lexical_absolute(supplied)
        else:
            windows = PureWindowsPath(os.fspath(path_or_relative))
            posix = PurePosixPath(os.fspath(path_or_relative).replace("\\", "/"))
            if windows.drive or posix.is_absolute() or any(part == ".." for part in posix.parts):
                raise PathSafetyError("held directory path escapes the store")
            directory = self.root.joinpath(*posix.parts)
        try:
            directory.relative_to(self.root)
        except ValueError as exc:
            raise PathSafetyError("held directory path escapes the store") from exc
        return directory

    @contextmanager
    def hold_directory_chain(
        self,
        path_or_relative: str | Path = ".",
    ) -> Iterator[_HeldDirectoryBoundary]:
        """Hold the store's non-reparse directory chain for containment.

        On Windows this prevents the held directory or any ancestor from being
        renamed. It does not prevent other processes from creating or deleting
        child entries inside the directory.
        """

        directory = self._directory_path(path_or_relative)
        with _hold_directory_tree(
            directory,
            authorized_root=self.authorized_root,
            create=False,
        ) as boundary:
            self._assert_store_identity()
            yield boundary

    @staticmethod
    def _expected_receipt(relative_path: str, payload: bytes) -> Receipt:
        return Receipt(relative_path, hashlib.sha256(payload).hexdigest(), len(payload))

    def write_once(self, relative_path: str, payload: bytes) -> Receipt:
        if not isinstance(payload, bytes):
            raise TypeError("raw payload must be bytes")
        normalized, target = self._target(relative_path)
        with _hold_directory_tree(
            target.parent,
            authorized_root=self.authorized_root,
            create=True,
        ) as boundary:
            self._assert_store_identity()
            descriptor, temporary_value = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
            )
            temporary = Path(temporary_value)
            try:
                temporary_metadata = _lstat_no_alias(temporary, label="temporary artifact")
                if not stat.S_ISREG(temporary_metadata.st_mode):
                    raise PathSafetyError("temporary artifact is not a regular file")
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = -1
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                boundary.assert_current()
                if os.name == "nt":
                    # The held target-parent boundary prevents path replacement.
                    # Windows rename is atomic and fails if the target exists.
                    os.rename(temporary, target)
                else:
                    os.link(temporary, target, follow_symlinks=False)
                boundary.assert_current()
            except FileExistsError as exc:
                raise ImmutableWriteError(f"artifact already exists: {normalized}") from exc
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        receipt = self._expected_receipt(normalized, payload)
        self.verify(receipt)
        return receipt

    def publish_or_verify(self, relative_path: str, payload: bytes) -> Receipt:
        """Publish new bytes or accept an existing exact immutable artifact."""

        if not isinstance(payload, bytes):
            raise TypeError("raw payload must be bytes")
        normalized, _ = self._target(relative_path)
        expected = self._expected_receipt(normalized, payload)
        try:
            return self.write_once(normalized, payload)
        except ImmutableWriteError as exc:
            try:
                self.verify(expected)
            except TamperError as mismatch:
                raise ImmutableWriteError(
                    f"artifact already exists with different bytes: {normalized}"
                ) from mismatch
            return expected

    def _read_regular_file(self, target: Path, maximum_bytes: int | None = None) -> bytes:
        if maximum_bytes is not None and (
            isinstance(maximum_bytes, bool)
            or not isinstance(maximum_bytes, int)
            or maximum_bytes < 1
        ):
            raise ValueError("maximum_bytes must be a positive integer")
        target = _lexical_absolute(target)
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PathSafetyError("artifact read escapes the store") from exc
        with _hold_directory_tree(
            target.parent,
            authorized_root=self.authorized_root,
            create=False,
        ) as boundary:
            self._assert_store_identity()
            before = _lstat_no_alias(target, label="artifact")
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise TamperError(f"artifact is not a unique regular file: {target.name}")
            if maximum_bytes is not None and before.st_size > maximum_bytes:
                raise TamperError(f"artifact exceeds {maximum_bytes} bytes: {target.name}")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(target, flags)
            except OSError as exc:
                raise TamperError(f"artifact could not be opened safely: {target.name}") from exc
            try:
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                    raise TamperError(f"opened artifact is not a unique regular file: {target.name}")
                if _snapshot(opened) != _snapshot(before):
                    raise TamperError(f"artifact changed before it was opened: {target.name}")
                if maximum_bytes is not None and opened.st_size > maximum_bytes:
                    raise TamperError(f"artifact exceeds {maximum_bytes} bytes: {target.name}")
                with os.fdopen(descriptor, "rb", closefd=False) as handle:
                    payload = handle.read() if maximum_bytes is None else handle.read(maximum_bytes + 1)
                after_read = os.fstat(descriptor)
                if _snapshot(after_read) != _snapshot(opened) or len(payload) != opened.st_size:
                    raise TamperError(f"artifact changed while it was read: {target.name}")
                if maximum_bytes is not None and len(payload) > maximum_bytes:
                    raise TamperError(f"artifact exceeds {maximum_bytes} bytes: {target.name}")
            finally:
                os.close(descriptor)
            boundary.assert_current()
            after = _lstat_no_alias(target, label="artifact")
            if _snapshot(after) != _snapshot(after_read):
                raise TamperError(f"artifact changed while it was read: {target.name}")
            return payload

    def verify(self, receipt: Receipt) -> bool:
        _, target = self._target(receipt.relative_path)
        try:
            payload = self._read_regular_file(target)
        except FileNotFoundError as exc:
            raise TamperError(f"artifact is missing: {receipt.relative_path}") from exc
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != receipt.byte_count or digest != receipt.sha256:
            raise TamperError(f"artifact does not match receipt: {receipt.relative_path}")
        return True
