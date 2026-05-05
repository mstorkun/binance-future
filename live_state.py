# -*- coding: utf-8 -*-
"""
live_state.py - Asenkron ve Atomik State Yönetimi (L3 Production Standard)

Bu modül Binance API ve WebSocket dinleyicilerini disk I/O işlemlerinden 
korumak için asenkron (non-blocking) olarak tasarlanmıştır. 
Olası elektrik kesintileri veya çökme (crash) durumlarına karşı:
1. fsync ile donanım (OS) seviyesinde diske yazma garantisi sunar.
2. 5'li Ring Backup rotasyonu (backup.1 ... backup.5) yapar.
3. asyncio.Lock ile yarış durumlarını (race conditions) engeller.
"""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import config

logger = logging.getLogger("binance_bot.live_state")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or getattr(config, "LIVE_STATE_FILE", "live_state.json"))
    if not target.exists():
        backup = _load_latest_backup(target)
        if backup is not None:
            logger.error(f"Live state primary missing, backup kullaniliyor: {target}")
            return backup
        return _empty_state()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        backup = _load_latest_backup(target)
        if backup is not None:
            logger.error(f"Live state okunamadi, backup kullaniliyor: {exc}")
            return backup
        logger.error(f"Live state okunamadi: {exc}")
        if bool(getattr(config, "LIVE_STATE_FAIL_CLOSED", True)):
            raise RuntimeError(f"Live state corrupted and no valid backup exists: {target}") from exc
        return _empty_state()
    data.setdefault("positions", {})
    data.setdefault("created_at", utc_now())
    return data


def save_state(state: dict[str, Any], path: str | Path | None = None) -> None:
    target = Path(path or getattr(config, "LIVE_STATE_FILE", "live_state.json"))
    state["updated_at"] = utc_now()
    state["symbols"] = list(getattr(config, "SYMBOLS", []))
    state["testnet"] = bool(getattr(config, "TESTNET", True))
    if target.parent and str(target.parent) != ".":
        target.parent.mkdir(parents=True, exist_ok=True)
    _rotate_backups(target)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(_clean(state), indent=2, sort_keys=True))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
    _fsync_parent(target)


def load_positions(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    return dict(load_state(path).get("positions") or {})


def save_positions(positions: dict[str, dict[str, Any]], path: str | Path | None = None) -> None:
    state = load_state(path)
    state["positions"] = positions
    save_state(state, path)


def upsert_position(symbol: str, position: dict[str, Any], path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    positions = load_positions(path)
    positions[symbol] = _clean_position(position)
    save_positions(positions, path)
    return positions


def remove_position(symbol: str, path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    positions = load_positions(path)
    positions.pop(symbol, None)
    save_positions(positions, path)
    return positions


def clear_positions(path: str | Path | None = None) -> None:
    save_positions({}, path)


def reconcile_positions(
    local_positions: dict[str, dict[str, Any]],
    exchange_positions: list[dict[str, Any]],
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    open_symbols = {_normalize_symbol(_position_symbol(pos)) for pos in exchange_positions if _contracts(pos) != 0}
    desired = {_normalize_symbol(sym) for sym in symbols}
    reconciled = {
        sym: pos
        for sym, pos in local_positions.items()
        if _normalize_symbol(sym) in open_symbols and _normalize_symbol(sym) in desired
    }
    removed = sorted(set(local_positions) - set(reconciled))
    return reconciled, removed


def _empty_state() -> dict[str, Any]:
    return {
        "created_at": utc_now(),
        "positions": {},
        "symbols": list(getattr(config, "SYMBOLS", [])),
        "testnet": bool(getattr(config, "TESTNET", True)),
    }


def _legacy_backup_path(target: Path, index: int) -> Path:
    return target.with_name(f"{target.name}.bak{index}")


def _manager_backup_path(target: Path, index: int) -> Path:
    return target.with_suffix(f"{target.suffix}.bak.{index}")


def _rotate_backups(target: Path) -> None:
    if not target.exists():
        return
    count = max(0, int(getattr(config, "LIVE_STATE_BACKUP_COUNT", 5)))
    if count <= 0:
        return
    for idx in range(count, 1, -1):
        src = _legacy_backup_path(target, idx - 1)
        dst = _legacy_backup_path(target, idx)
        if src.exists():
            os.replace(src, dst)
    os.replace(target, _legacy_backup_path(target, 1))


def _load_latest_backup(target: Path) -> dict[str, Any] | None:
    count = max(0, int(getattr(config, "LIVE_STATE_BACKUP_COUNT", 5)))
    for path_factory in (_legacy_backup_path, _manager_backup_path):
        for idx in range(1, count + 1):
            backup = path_factory(target, idx)
            if not backup.exists():
                continue
            try:
                data = json.loads(backup.read_text(encoding="utf-8"))
            except Exception:
                continue
            data.setdefault("positions", {})
            data.setdefault("created_at", utc_now())
            return data
    return None


def _fsync_parent(target: Path) -> None:
    try:
        fd = os.open(str(target.parent if str(target.parent) != "." else Path(".")), os.O_RDONLY)
    except Exception:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _clean_position(position: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _clean(v) for k, v in position.items()}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _position_symbol(pos: dict[str, Any]) -> str:
    return str(pos.get("symbol") or (pos.get("info") or {}).get("symbol") or "")


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").split(":")[0].upper()


def _contracts(pos: dict[str, Any]) -> float:
    try:
        return float(pos.get("contracts") or pos.get("positionAmt") or (pos.get("info") or {}).get("positionAmt") or 0)
    except (TypeError, ValueError):
        return 0.0


class LiveStateManager:
    def __init__(self, state_file_path: str = "live_state.json", max_backups: int = 5):
        self.state_file = Path(state_file_path)
        self.max_backups = max_backups
        self._lock = asyncio.Lock()

    async def save_state(self, state_data: Dict[str, Any]) -> None:
        """
        State verisini asenkron ve atomik olarak güvenle kaydeder.
        Event loop'u bloklamamak için I/O işlemleri thread pool'a devredilir.
        """
        async with self._lock:
            tmp_file = self.state_file.with_suffix('.json.tmp')
            
            # CPU-bound: JSON serialize
            try:
                json_str = json.dumps(state_data, indent=2, ensure_ascii=False)
            except TypeError as e:
                logger.error(f"State serileştirme hatası (JSON uyumsuz veri): {e}")
                raise

            # Disk-bound: Yazma, Fsync ve Yedekleme işlemlerini bloklamadan çalıştır
            try:
                await asyncio.to_thread(self._sync_write_and_rotate, tmp_file, json_str)
            except Exception as e:
                logger.error(f"State kaydedilirken kritik donanım/IO hatası: {e}")
                # Temizlik
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)
                raise

    def _sync_write_and_rotate(self, tmp_file: Path, json_str: str) -> None:
        """
        Senkron bağlamda:
        1. Temp dosyaya yaz + fsync
        2. Eski yedekleri kaydır (Ring rotation)
        3. Temp dosyayı asıl dosyayla atomik yer değiştir (os.replace)
        """
        # 1. fsync garantili yazım
        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
            f.flush()          # Python buffer'ı işletim sistemine aktar
            os.fsync(f.fileno()) # OS buffer'ı fiziksel diske zorla yaz (P0 gereksinimi)

        # 2. Ring Backup Rotasyonu (P0 gereksinimi)
        self._rotate_backups_sync()

        # 3. Atomik Yer Değiştirme (POSIX ve Windows'ta atomic)
        if tmp_file.exists():
            os.replace(tmp_file, self.state_file)

    def _rotate_backups_sync(self) -> None:
        """
        5-li ring backup rotasyonunu uygular:
        live_state.json.bak.4 -> live_state.json.bak.5
        live_state.json.bak.3 -> live_state.json.bak.4 ...
        live_state.json -> live_state.json.bak.1
        """
        if not self.state_file.exists():
            return
            
        # Eski yedekleri sondan başa doğru kaydır
        for i in range(self.max_backups - 1, 0, -1):
            src = self.state_file.with_suffix(f'.json.bak.{i}')
            dst = self.state_file.with_suffix(f'.json.bak.{i+1}')
            if src.exists():
                os.replace(src, dst)
                
        # Geçerli ana dosyayı ilk yedek olarak kopyala
        first_backup = self.state_file.with_suffix('.json.bak.1')
        shutil.copy2(self.state_file, first_backup)

    async def load_state(self) -> Dict[str, Any]:
        """
        Ana state dosyasını okur. Dosya bozuksa veya yoksa boş dict döner.
        Gelecekte backup dosyalarından auto-recovery mantığı eklenebilir.
        """
        async with self._lock:
            if not self.state_file.exists():
                return {}
                
            def _read_sync() -> Dict[str, Any]:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            try:
                return await asyncio.to_thread(_read_sync)
            except json.JSONDecodeError as e:
                logger.error(f"Ana state dosyası okunamıyor (JSON bozuk): {e}")
                # TODO: fallback to .bak.1 
                raise
            except Exception as e:
                logger.error(f"State dosyası yüklenirken hata: {e}")
                raise
