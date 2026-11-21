from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent
from app.services.observer import (
    EventType,
    NotificationManager,
    ScheduleEvent,
    notification_manager,
)


class OutboxDispatcher:
    """Menulis event ke tabel Outbox dalam transaksi DB dan mengirimnya setelah commit secara idempoten."""

    _dispatched_event_ids: set[str] = set()

    @classmethod
    def reset_idempotency_cache(cls) -> None:
        cls._dispatched_event_ids.clear()

    @staticmethod
    def enqueue_event(
        db: Session,
        event: ScheduleEvent,
        invalidated_krs_ids: list[int] | None = None,
    ) -> OutboxEvent:
        """Menyimpan OutboxEvent ke session aktif (belum di-commit agar atomik dengan perubahan jadwal)."""
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "jadwal_id": event.jadwal_id,
            "before": event.before,
            "after": event.after,
            "invalidated_krs_ids": invalidated_krs_ids or [],
        }
        record = OutboxEvent(
            event_id=event.event_id,
            event_type=event.event_type.value,
            jadwal_id=event.jadwal_id,
            payload_json=json.dumps(payload, default=str),
            status="PENDING",
        )
        db.add(record)
        return record

    @classmethod
    def dispatch_event_record(
        cls,
        db: Session,
        record: OutboxEvent,
        manager: NotificationManager = notification_manager,
    ) -> bool:
        """Mengirim satu OutboxEvent setelah commit; mengabaikan event_id yang sudah pernah terkirim."""
        if record.status == "SENT" or record.event_id in cls._dispatched_event_ids:
            return False

        payload = json.loads(record.payload_json)
        event = ScheduleEvent(
            event_type=EventType(record.event_type),
            jadwal_id=record.jadwal_id,
            before=payload.get("before"),
            after=payload.get("after"),
            event_id=record.event_id,
        )

        manager.dispatch(event)

        record.status = "SENT"
        record.processed_at = datetime.now(timezone.utc)
        cls._dispatched_event_ids.add(record.event_id)
        db.commit()
        return True

    @classmethod
    def dispatch_pending(
        cls,
        db: Session,
        manager: NotificationManager = notification_manager,
    ) -> int:
        """Memproses seluruh OutboxEvent berstatus PENDING setelah transaksi utama ter-commit."""
        pending_records = list(
            db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING")
                .order_by(OutboxEvent.id)
            ).all()
        )
        sent_count = 0
        for record in pending_records:
            if cls.dispatch_event_record(db, record, manager=manager):
                sent_count += 1
        return sent_count