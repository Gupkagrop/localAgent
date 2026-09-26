"""
Модуль Audio Ducking для автоматического приглушения фонового звука Windows.
Использует Windows Core Audio API через pycaw.
"""
import threading
from typing import Optional
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

class AudioDucker:
    def __init__(self):
        self._lock = threading.Lock()
        self._previous_volume: Optional[float] = None
        self._is_ducked: bool = False

    def _get_volume_endpoint(self) -> Optional[IAudioEndpointVolume]:
        """Получает COM-интерфейс управления мастер-громкостью Windows."""
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return interface.QueryInterface(IAudioEndpointVolume)
        except Exception:
            return None

    def duck(self, duck_factor: float = 0.20) -> None:
        """Приглушает системный звук на время записи голоса."""
        with self._lock:
            if self._is_ducked:
                return

            endpoint = self._get_volume_endpoint()
            if endpoint is None:
                return

            try:
                current_vol = endpoint.GetMasterVolumeLevelScalar()
                self._previous_volume = current_vol
                # Понижаем громкость до доли от текущей (минимум 5%)
                target_vol = max(0.05, current_vol * duck_factor)
                endpoint.SetMasterVolumeLevelScalar(target_vol, None)
                self._is_ducked = True
            except Exception:
                pass

    def unduck(self) -> None:
        """Восстанавливает прежний уровень громкости Windows."""
        with self._lock:
            if not self._is_ducked or self._previous_volume is None:
                return

            endpoint = self._get_volume_endpoint()
            if endpoint is not None:
                try:
                    endpoint.SetMasterVolumeLevelScalar(self._previous_volume, None)
                except Exception:
                    pass
            self._is_ducked = False
            self._previous_volume = None

    def set_volume(self, percent: float) -> bool:
        """Устанавливает абсолютный уровень громкости от 0.0 до 1.0."""
        endpoint = self._get_volume_endpoint()
        if endpoint is None:
            return False
        try:
            scalar = max(0.0, min(1.0, percent))
            endpoint.SetMasterVolumeLevelScalar(scalar, None)
            return True
        except Exception:
            return False

    def get_volume(self) -> float:
        """Возвращает текущую громкость в процентах (0-100)."""
        endpoint = self._get_volume_endpoint()
        if endpoint is None:
            return 50.0
        try:
            return endpoint.GetMasterVolumeLevelScalar() * 100.0
        except Exception:
            return 50.0
