from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

logger = logging.getLogger("pmb.notifications")


class EventType(StrEnum):
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_CHANGED = "SCHEDULE_CHANGED"
    SCHEDULE_DELETED = "SCHEDULE_DELETED"


@dataclass(frozen=True)
class ScheduleEvent:
    """Objek event immutable yang dikirim oleh ScheduleSubject ke seluruh Observer."""

    event_type: EventType
    jadwal_id: int
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    event_id: str = field(default_factory=lambda: uuid4().hex)


class Observer(Protocol):
    def update(self, event: ScheduleEvent) -> None: ...


class LogNotificationChannel:
    """Simulasi kanal pengiriman notifikasi (Email, SMS, Push) berbasis log."""

    def __init__(self, channel_name: str, sink: list[dict[str, Any]]) -> None:
        self.channel_name = channel_name.upper()
        self._sink = sink

    def send(self, recipient: str, subject: str, message: str, event_id: str) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": event_id,
            "channel": self.channel_name,
            "recipient": recipient,
            "subject": subject,
            "message": message,
        }
        self._sink.append(entry)
        logger.info(
            "[%s] -> %s | %s: %s (event_id=%s)",
            self.channel_name,
            recipient,
            subject,
            message,
            event_id,
        )


class ScheduleSubject:
    """Subject pada Observer Pattern yang mengelola subscriber dan notifikasi tahan gagal."""

    def __init__(self) -> None:
        self._observers: list[Observer] = []
        self.errors: list[dict[str, str]] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: ScheduleEvent) -> None:
        # Iterasi salinan daftar observer + isolasi error per observer
        for observer in list(self._observers):
            try:
                observer.update(event)
            except Exception as exc:  # noqa: BLE001
                observer_name = type(observer).__name__
                logger.exception(
                    "Observer %s gagal memproses event %s", observer_name, event.event_id
                )
                self.errors.append(
                    {
                        "event_id": event.event_id,
                        "observer": observer_name,
                        "error": str(exc),
                    }
                )


class StudentObserver:
    """Observer untuk mahasiswa peserta kelas terdampak (kanal Push & Email)."""

    def __init__(
        self,
        push_channel: LogNotificationChannel,
        email_channel: LogNotificationChannel,
    ) -> None:
        self.push_channel = push_channel
        self.email_channel = email_channel

    def update(self, event: ScheduleEvent) -> None:
        data = event.after or event.before or {}
        kelas_id = data.get("kelas_id", "-")
        recipient = f"mahasiswa-kelas-{kelas_id}"
        msg = (
            f"Perubahan jadwal ({event.event_type}) pada Jadwal #{event.jadwal_id} "
            f"(Kelas #{kelas_id}). Silakan periksa status KRS Anda."
        )
        self.push_channel.send(recipient, "Notifikasi Jadwal Mahasiswa", msg, event.event_id)
        self.email_channel.send(recipient, "Perubahan Jadwal Kuliah", msg, event.event_id)


class LecturerObserver:
    """Observer untuk dosen pengampu lama maupun baru (kanal SMS & Email)."""

    def __init__(
        self,
        sms_channel: LogNotificationChannel,
        email_channel: LogNotificationChannel,
    ) -> None:
        self.sms_channel = sms_channel
        self.email_channel = email_channel

    def update(self, event: ScheduleEvent) -> None:
        dosen_ids: list[Any] = []
        if event.before and event.before.get("dosen_id") is not None:
            dosen_ids.append(event.before["dosen_id"])
        if event.after and event.after.get("dosen_id") is not None:
            if event.after["dosen_id"] not in dosen_ids:
                dosen_ids.append(event.after["dosen_id"])

        for dosen_id in dosen_ids or ["-"]:
            recipient = f"dosen-{dosen_id}"
            msg = (
                f"Info Mengajar ({event.event_type}): Jadwal #{event.jadwal_id} "
                f"mengalami pembaruan waktu/ruangan."
            )
            self.sms_channel.send(recipient, "SMS Jadwal Dosen", msg, event.event_id)
            self.email_channel.send(recipient, "Pembaruan Jadwal Mengajar", msg, event.event_id)


class AdminObserver:
    """Observer untuk admin akademik guna mencatat jejak audit perubahan jadwal (kanal Email)."""

    def __init__(self, email_channel: LogNotificationChannel) -> None:
        self.email_channel = email_channel

    def update(self, event: ScheduleEvent) -> None:
        msg = (
            f"Audit Jadwal #{event.jadwal_id} [{event.event_type}] | "
            f"Before={event.before} -> After={event.after}"
        )
        self.email_channel.send(
            "admin-akademik@kampus.ac.id",
            "Audit Perubahan Jadwal",
            msg,
            event.event_id,
        )


class NotificationManager:
    """Fasad pengelola ScheduleSubject, 3 Observer default, dan penyimpanan log kanal."""

    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []
        self.email_channel = LogNotificationChannel("EMAIL", self.logs)
        self.sms_channel = LogNotificationChannel("SMS", self.logs)
        self.push_channel = LogNotificationChannel("PUSH", self.logs)

        self.subject = ScheduleSubject()
        self.student_observer = StudentObserver(self.push_channel, self.email_channel)
        self.lecturer_observer = LecturerObserver(self.sms_channel, self.email_channel)
        self.admin_observer = AdminObserver(self.email_channel)

        self.subject.attach(self.student_observer)
        self.subject.attach(self.lecturer_observer)
        self.subject.attach(self.admin_observer)

    def clear_logs(self) -> None:
        self.logs.clear()
        self.subject.errors.clear()

    def dispatch(self, event: ScheduleEvent) -> None:
        self.subject.notify(event)


notification_manager = NotificationManager()