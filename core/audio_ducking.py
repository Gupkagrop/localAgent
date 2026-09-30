"""
Модуль Audio Ducking для автоматического приглушения фонового звука Windows.
Использует Windows Core Audio API через pycaw.
"""
import logging
import threading
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

logger = logging.getLogger("AudioDucker")


class AudioDucker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._previous_volume: float | None = None
        self._is_ducked: bool = False

    def _get_volume_endpoint(self) -> IAudioEndpointVolume | None:
        """Получает COM-интерфейс управления мастер-громкостью Windows с безопасной инициализацией COM."""
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception as e:
            logger.debug("COM CoInitialize: %s", e)

        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return interface.QueryInterface(IAudioEndpointVolume)
        except Exception as e:
            logger.debug("Не удалось получить IAudioEndpointVolume: %s", e)
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
                # Понижаем громкость до доли от текущей (если звук был выключен — оставляем 0, иначе минимум 5%)
                if current_vol <= 0.001:
                    target_vol = 0.0
                else:
                    target_vol = max(0.05, current_vol * duck_factor)
                endpoint.SetMasterVolumeLevelScalar(target_vol, None)
                self._is_ducked = True
            except Exception as e:
                logger.warning("Не удалось приглушить системный звук (duck): %s", e)

    def unduck(self) -> None:
        """Восстанавливает прежний уровень громкости Windows."""
        with self._lock:
            if not self._is_ducked or self._previous_volume is None:
                return

            endpoint = self._get_volume_endpoint()
            if endpoint is not None:
                try:
                    endpoint.SetMasterVolumeLevelScalar(self._previous_volume, None)
                except Exception as e:
                    logger.warning("Не удалось восстановить громкость (unduck): %s", e)
            self._is_ducked = False
            self._previous_volume = None

    def set_volume(self, value: float) -> bool:
        """
        Устанавливает абсолютный уровень громкости.
        Поддерживает как скалярное значение (0.0..1.0), так и процентное (0..100).
        """
        endpoint = self._get_volume_endpoint()
        if endpoint is None:
            return False
        try:
            # Если передано значение > 1.0, трактуем как процентное (0..100)
            scalar = value / 100.0 if value > 1.0 else value
            clamped = max(0.0, min(1.0, float(scalar)))
            endpoint.SetMasterVolumeLevelScalar(clamped, None)
            return True
        except Exception as e:
            logger.warning("Не удалось установить громкость (%s): %s", value, e)
            return False

    def get_volume(self) -> float:
        """Возвращает текущую громкость в процентах (0-100)."""
        endpoint = self._get_volume_endpoint()
        if endpoint is None:
            return 50.0
        try:
            return endpoint.GetMasterVolumeLevelScalar() * 100.0
        except Exception as e:
            logger.warning("Не удалось получить текущую громкость: %s", e)
            return 50.0
