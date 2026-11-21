# UML Sequence Diagram — Observer Pattern, Outbox, & Invalidasi KRS (Minggu 8)

Diagram berikut menggambarkan alur perubahan jadwal (`PUT /api/jadwal/{jadwal_id}`), pencatatan *OutboxEvent* dan invalidasi KRS terdampak (`Actor.SISTEM -> REVISION`) dalam satu transaksi database yang atomik, serta pengiriman notifikasi lintas kanal (`EMAIL`, `SMS`, `PUSH`) **setelah `db.commit()`**.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Admin Akademik
    participant Router as FastAPI Router (/api/jadwal)
    participant Service as SchedulingService
    participant Invalidator as KRSInvalidator
    participant Outbox as OutboxDispatcher
    participant DB as SQLite Database
    participant Subject as ScheduleSubject
    participant StudentObs as StudentObserver
    participant LecturerObs as LecturerObserver
    participant AdminObs as AdminObserver

    Admin->>Router: PUT /api/jadwal/{id} (payload baru)
    Router->>Service: update_jadwal(db, jadwal_id, payload)
    Service->>DB: SELECT ... FOR UPDATE (Kelas, Ruangan, Dosen, Jadwal)
    Service->>Service: _check_capacity() & _check_3d_conflicts()
    Service->>DB: UPDATE jadwal (hari, jam, ruangan, dosen)

    Service->>Invalidator: invalidate_affected_krs(db, kelas_id, reason)
    Invalidator->>DB: SELECT KRS WHERE status IN ('SUBMITTED', 'APPROVED')
    Invalidator->>Invalidator: validate_transition(Actor.SISTEM, status, 'REVISION')
    Invalidator->>DB: UPDATE krs SET status = 'REVISION'
    Invalidator-->>Service: invalidated_krs_ids

    Service->>Outbox: enqueue_event(db, ScheduleEvent, invalidated_krs_ids)
    Outbox->>DB: INSERT INTO outbox_events (status='PENDING')

    Service->>DB: COMMIT TRANSACTION
    Note over Service,DB: Perubahan jadwal, status KRS, & Outbox tersimpan atomik

    Service->>Outbox: dispatch_pending(db)
    Outbox->>DB: SELECT * FROM outbox_events WHERE status = 'PENDING'
    Outbox->>Subject: notify(ScheduleEvent)

    par Isolasi Error per Observer
        Subject->>StudentObs: update(event)
        StudentObs-->>StudentObs: Kirim PUSH & EMAIL (Log)
    and
        Subject->>LecturerObs: update(event)
        LecturerObs-->>LecturerObs: Kirim SMS & EMAIL (Log)
    and
        Subject->>AdminObs: update(event)
        AdminObs-->>AdminObs: Kirim EMAIL Audit (Log)
    end

    Outbox->>DB: UPDATE outbox_events SET status = 'SENT', processed_at = NOW()
    Outbox->>DB: COMMIT
    Service-->>Router: JadwalResponse (200 OK)
    Router-->>Admin: JSON Jadwal Terbaru + Notifikasi Terkirim