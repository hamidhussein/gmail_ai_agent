"""
GmailAI Assistant - Database Repository Pattern
"""
import json
import logging
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import create_engine, func, desc, or_, and_
from sqlalchemy.orm import sessionmaker, scoped_session, Session

from app.config import config_manager
from database.models import (
    Base,
    Account,
    EmailRecord,
    CleanupSuggestion,
    SenderProfile,
    ActionAuditLog,
    DailyDigestRecord,
    UserSafetyRule,
)
from app.constants import EmailCategory, ActionType, SuggestionStatus

logger = logging.getLogger("GmailAI.Repository")


def _utcnow() -> datetime.datetime:
    """Returns a naive UTC datetime suitable for SQLite storage."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Repository:
    """Thread-safe database repository using SQLite + SQLAlchemy."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config_manager.db_path
        self.db_url = f"sqlite:///{self.db_path.as_posix()}"
        self.engine = create_engine(
            self.db_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.Session = scoped_session(self.session_factory)
        self.init_schema()

    def init_schema(self) -> None:
        """Creates all database tables."""
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized at {self.db_path}")

    def get_session(self) -> Session:
        return self.Session()

    # ----------------- Account Operations -----------------

    def get_active_account(self) -> Optional[Account]:
        session = self.get_session()
        try:
            return session.query(Account).filter_by(is_active=True).first()
        finally:
            session.close()

    def get_or_create_account(self, email: str, display_name: Optional[str] = None) -> Account:
        session = self.get_session()
        try:
            acc = session.query(Account).filter_by(email=email).first()
            if not acc:
                acc = Account(email=email, display_name=display_name, is_active=True)
                session.add(acc)
                session.commit()
                session.refresh(acc)
            return acc
        except Exception as e:
            session.rollback()
            logger.error(f"Error getting/creating account {email}: {e}")
            raise
        finally:
            session.close()

    def list_accounts(self) -> List[Account]:
        session = self.get_session()
        try:
            return session.query(Account).all()
        finally:
            session.close()

    def set_active_account(self, email: str) -> None:
        session = self.get_session()
        try:
            session.query(Account).update({Account.is_active: False})
            session.query(Account).filter_by(email=email).update({Account.is_active: True})
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting active account {email}: {e}")
            raise
        finally:
            session.close()

    def update_account_synced_at(self, email: str) -> None:
        """Updates last_synced_at timestamp for the account with the given email."""
        session = self.get_session()
        try:
            session.query(Account).filter_by(email=email).update(
                {Account.last_synced_at: _utcnow()}
            )
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating last_synced_at for {email}: {e}")
        finally:
            session.close()

    def deactivate_account(self, email: str) -> bool:
        """Persists account deactivation and clears any legacy database token."""
        session = self.get_session()
        try:
            updated = session.query(Account).filter_by(email=email).update(
                {Account.is_active: False, Account.token_encrypted: None}
            )
            session.commit()
            return bool(updated)
        except Exception as e:
            session.rollback()
            logger.error(f"Error deactivating account {email}: {e}")
            raise
        finally:
            session.close()

    def disconnect_all_accounts(self) -> int:
        """
        Disconnects every connected Gmail account: deletes the encrypted OAuth
        token on disk, clears the stored token, and deactivates the account
        record. Returns the number of accounts disconnected.
        """
        # Lazy import avoids a circular dependency at module load time.
        try:
            from authentication.token_manager import token_manager
        except Exception:
            token_manager = None

        session = self.get_session()
        count = 0
        try:
            accounts = session.query(Account).all()
            for acc in accounts:
                if token_manager is not None:
                    try:
                        token_manager.delete_token(acc.email)
                    except Exception as e:
                        logger.warning(f"Could not delete token for {acc.email}: {e}")
                acc.is_active = False
                acc.token_encrypted = None
                count += 1
            session.commit()
            logger.info(f"Disconnected {count} account(s).")
        except Exception as e:
            session.rollback()
            logger.error(f"Error disconnecting accounts: {e}")
        finally:
            session.close()
        return count

    # ----------------- Email Operations -----------------

    @staticmethod
    def _filter_email_fields(email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filters a dictionary so only valid EmailRecord columns are included."""
        valid_cols = {c.name for c in EmailRecord.__table__.columns}
        return {k: v for k, v in email_data.items() if k in valid_cols}

    def save_or_update_email(self, email_data: Dict[str, Any]) -> EmailRecord:
        """Upserts an email record by its Gmail message_id."""
        session = self.get_session()
        try:
            clean_data = self._filter_email_fields(email_data)
            msg_id = clean_data["message_id"]
            record = session.query(EmailRecord).filter_by(message_id=msg_id).first()
            if not record:
                record = EmailRecord(**clean_data)
                session.add(record)
            else:
                for k, v in clean_data.items():
                    if k != "id":
                        setattr(record, k, v)
                record.updated_at = _utcnow()

            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving email: {e}")
            raise
        finally:
            session.close()

    def save_emails_batch(self, emails_list: List[Dict[str, Any]]) -> int:
        """
        True bulk upsert — processes all emails in a single DB session.
        Falls back to per-item save on partial failures so partial success is preserved.
        """
        session = self.get_session()
        saved_count = 0
        try:
            existing_ids = {
                row[0]
                for row in session.query(EmailRecord.message_id).all()
            }
            new_records = []
            update_records = []

            for raw_data in emails_list:
                email_data = self._filter_email_fields(raw_data)
                if email_data.get("message_id") in existing_ids:
                    update_records.append(email_data)
                else:
                    new_records.append(email_data)

            # Bulk insert new records
            if new_records:
                session.bulk_insert_mappings(EmailRecord, new_records)

            # Update existing records individually within the same session
            for email_data in update_records:
                msg_id = email_data["message_id"]
                record = session.query(EmailRecord).filter_by(message_id=msg_id).first()
                if record:
                    for k, v in email_data.items():
                        if k != "id":
                            setattr(record, k, v)
                    record.updated_at = _utcnow()

            session.commit()
            saved_count = len(emails_list)
        except Exception as e:
            session.rollback()
            logger.error(f"Bulk save failed, retrying individually: {e}")
            session.close()
            # Fallback: individual saves to preserve partial success
            for email_data in emails_list:
                try:
                    self.save_or_update_email(email_data)
                    saved_count += 1
                except Exception as item_err:
                    logger.error(f"Failed to save email {email_data.get('message_id')}: {item_err}")
            return saved_count
        finally:
            session.close()
        return saved_count

    def update_email_flags(self, message_id: str, **flags: Any) -> None:
        """
        Updates boolean flag columns on an EmailRecord safely within its own session.
        Example: update_email_flags(msg_id, is_archived=True, is_unread=False)
        """
        allowed_flags = {
            "is_archived", "is_unread", "is_starred", "is_trash",
            "category", "importance_score", "suggested_action",
        }
        updates = {k: v for k, v in flags.items() if k in allowed_flags}
        if not updates:
            return
        session = self.get_session()
        try:
            updates["updated_at"] = _utcnow()
            session.query(EmailRecord).filter_by(message_id=message_id).update(updates)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating email flags for {message_id}: {e}")
        finally:
            session.close()

    def get_email_by_id(self, email_id: int) -> Optional[EmailRecord]:
        session = self.get_session()
        try:
            return session.query(EmailRecord).filter_by(id=email_id).first()
        finally:
            session.close()

    def get_email_by_message_id(self, message_id: str) -> Optional[EmailRecord]:
        session = self.get_session()
        try:
            return session.query(EmailRecord).filter_by(message_id=message_id).first()
        finally:
            session.close()

    def get_inbox_emails(
        self,
        account_id: Optional[int] = None,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        search: Optional[str] = None,
        is_unread: Optional[bool] = None,
        is_starred: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        min_importance: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EmailRecord]:
        session = self.get_session()
        try:
            q = session.query(EmailRecord).filter_by(is_trash=False)

            if is_archived is not None:
                q = q.filter(EmailRecord.is_archived == is_archived)
            if account_id:
                q = q.filter(EmailRecord.account_id == account_id)
            if category and category != "ALL":
                q = q.filter(EmailRecord.category == category)
            if is_unread is not None:
                q = q.filter(EmailRecord.is_unread == is_unread)
            if is_starred is not None:
                q = q.filter(EmailRecord.is_starred == is_starred)
            if min_importance is not None:
                q = q.filter(EmailRecord.importance_score >= min_importance)
            active_search = search_query or search
            if active_search:
                term = f"%{active_search}%"
                q = q.filter(
                    or_(
                        EmailRecord.subject.ilike(term),
                        EmailRecord.sender.ilike(term),
                        EmailRecord.sender_name.ilike(term),
                        EmailRecord.snippet.ilike(term),
                    )
                )

            return q.order_by(desc(EmailRecord.received_at)).offset(offset).limit(limit).all()
        finally:
            session.close()

    def get_inbox_stats(self, account_id: Optional[int] = None) -> Dict[str, int]:
        """Aggregates metrics for the Dashboard."""
        session = self.get_session()
        try:
            q = session.query(EmailRecord).filter_by(is_trash=False)
            if account_id:
                q = q.filter(EmailRecord.account_id == account_id)

            total = q.count()
            unread = q.filter(EmailRecord.is_unread == True).count()

            # Old emails (> 30 days)
            thirty_days_ago = _utcnow() - datetime.timedelta(days=30)
            old_count = q.filter(EmailRecord.received_at < thirty_days_ago).count()

            # High importance
            important_count = q.filter(EmailRecord.importance_score >= 70).count()

            # Need reply count
            reply_needed_count = q.filter(
                EmailRecord.suggested_action == ActionType.DRAFT_REPLY.value,
                EmailRecord.is_unread == True,
            ).count()

            # Cleanup suggested count
            cleanup_count = session.query(CleanupSuggestion).filter_by(
                status=SuggestionStatus.PENDING.value
            ).count()

            return {
                "total_emails": total,
                "unread_emails": unread,
                "old_emails": old_count,
                "important_emails": important_count,
                "reply_needed_emails": reply_needed_count,
                "cleanup_suggested_emails": cleanup_count,
            }
        finally:
            session.close()

    # ----------------- Suggestions Operations -----------------

    def create_suggestion(
        self, email_id: int, action_type: str, category: str, reason: str, confidence: float
    ) -> CleanupSuggestion:
        session = self.get_session()
        try:
            # Check if pending suggestion already exists
            existing = session.query(CleanupSuggestion).filter_by(
                email_id=email_id, status=SuggestionStatus.PENDING.value
            ).first()
            if existing:
                existing.action_type = action_type
                existing.category = category
                existing.reason = reason
                existing.confidence = confidence
                session.commit()
                return existing

            sugg = CleanupSuggestion(
                email_id=email_id,
                action_type=action_type,
                category=category,
                reason=reason,
                confidence=confidence,
                status=SuggestionStatus.PENDING.value,
            )
            session.add(sugg)
            session.commit()
            session.refresh(sugg)
            return sugg
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating suggestion: {e}")
            raise
        finally:
            session.close()

    def get_pending_suggestions(self, limit: int = 100) -> List[Tuple[CleanupSuggestion, EmailRecord]]:
        session = self.get_session()
        try:
            results = (
                session.query(CleanupSuggestion, EmailRecord)
                .join(EmailRecord, CleanupSuggestion.email_id == EmailRecord.id)
                .filter(CleanupSuggestion.status == SuggestionStatus.PENDING.value)
                .order_by(desc(CleanupSuggestion.confidence))
                .limit(limit)
                .all()
            )
            return results
        finally:
            session.close()

    get_pending_cleanup_suggestions = get_pending_suggestions

    def update_suggestion_status(self, suggestion_id: int, status: str) -> None:
        session = self.get_session()
        try:
            sugg = session.query(CleanupSuggestion).filter_by(id=suggestion_id).first()
            if sugg:
                sugg.status = status
                if status == SuggestionStatus.EXECUTED.value:
                    sugg.executed_at = _utcnow()
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating suggestion status: {e}")
            raise
        finally:
            session.close()

    # ----------------- Sender Profiles & Memory -----------------

    def get_or_create_sender_profile(self, email: str, name: Optional[str] = None) -> SenderProfile:
        session = self.get_session()
        try:
            clean_email = email.strip().lower()
            domain = clean_email.split("@")[-1] if "@" in clean_email else ""
            profile = session.query(SenderProfile).filter_by(email=clean_email).first()
            if not profile:
                profile = SenderProfile(
                    email=clean_email,
                    domain=domain,
                    name=name,
                    total_received=0,
                    total_opened=0,
                    total_replied=0,
                    learned_importance=50,
                )
                session.add(profile)
                session.commit()
                session.refresh(profile)
            return profile
        finally:
            session.close()

    def record_sender_interaction(
        self,
        email: str,
        name: Optional[str] = None,
        opened: bool = False,
        replied: bool = False,
        is_vip: Optional[bool] = None,
        override_category: Optional[str] = None,
    ) -> SenderProfile:
        session = self.get_session()
        try:
            clean_email = email.strip().lower()
            domain = clean_email.split("@")[-1] if "@" in clean_email else ""
            profile = session.query(SenderProfile).filter_by(email=clean_email).first()
            if not profile:
                profile = SenderProfile(
                    email=clean_email,
                    domain=domain,
                    name=name,
                    total_received=0,
                    total_opened=0,
                    total_replied=0,
                    learned_importance=50,
                )
                session.add(profile)

            profile.total_received = (profile.total_received or 0) + 1
            if opened:
                profile.total_opened = (profile.total_opened or 0) + 1
            if replied:
                profile.total_replied = (profile.total_replied or 0) + 1
            if is_vip is not None:
                profile.is_vip = is_vip
            if override_category:
                profile.override_category = override_category

            # Recalculate learned importance dynamically
            if profile.is_vip:
                profile.learned_importance = max(profile.learned_importance or 50, 90)
            elif (profile.total_received or 0) > 0:
                open_ratio = (profile.total_opened or 0) / profile.total_received
                reply_ratio = (profile.total_replied or 0) / profile.total_received
                profile.learned_importance = int(min(100, max(10, 40 + (open_ratio * 30) + (reply_ratio * 30))))

            profile.last_interacted_at = _utcnow()
            session.commit()
            session.refresh(profile)
            return profile
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating sender profile: {e}")
            raise
        finally:
            session.close()

    def update_sender_importance(self, email: str, delta: int) -> None:
        """
        Adjusts the learned_importance for a sender by delta (positive or negative).
        Clamped to [10, 100]. Used by the learning engine to persist user feedback.
        """
        session = self.get_session()
        try:
            clean_email = email.strip().lower()
            profile = session.query(SenderProfile).filter_by(email=clean_email).first()
            if profile:
                new_score = int(min(100, max(10, (profile.learned_importance or 50) + delta)))
                profile.learned_importance = new_score
                session.commit()
                logger.info(f"Updated sender importance for {clean_email}: {new_score}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating sender importance for {email}: {e}")
        finally:
            session.close()

    # ----------------- Action Audit Logging -----------------

    def log_action(
        self,
        action_type: str,
        email_message_id: Optional[str],
        account_email: Optional[str],
        subject: Optional[str],
        sender: Optional[str],
        reason: Optional[str],
        user_approved: bool = True,
        double_confirmed: bool = False,
    ) -> ActionAuditLog:
        session = self.get_session()
        try:
            entry = ActionAuditLog(
                action_type=action_type,
                email_message_id=email_message_id,
                account_email=account_email,
                subject=subject,
                sender=sender,
                reason=reason,
                user_approved=user_approved,
                double_confirmed=double_confirmed,
                executed_at=_utcnow(),
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)

            audit_logger = logging.getLogger("GmailAI.Audit")
            audit_logger.info(
                f"Action: {action_type} | MessageId: {email_message_id} | Sender: {sender} | "
                f"Approved: {user_approved} | Reason: {reason}"
            )
            return entry
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving audit log: {e}")
            raise
        finally:
            session.close()

    def get_recent_audit_logs(self, limit: int = 50) -> List[ActionAuditLog]:
        session = self.get_session()
        try:
            return session.query(ActionAuditLog).order_by(desc(ActionAuditLog.executed_at)).limit(limit).all()
        finally:
            session.close()

    # ----------------- Daily Digests -----------------

    def save_daily_digest(
        self,
        digest_date: str,
        total_emails: int,
        important_count: int,
        need_reply_count: int,
        meetings_count: int,
        cleanup_suggested_count: int,
        summary_markdown: str,
        stats_json: str = "{}",
    ) -> DailyDigestRecord:
        session = self.get_session()
        try:
            rec = session.query(DailyDigestRecord).filter_by(digest_date=digest_date).first()
            if not rec:
                rec = DailyDigestRecord(
                    digest_date=digest_date,
                    total_emails=total_emails,
                    important_count=important_count,
                    need_reply_count=need_reply_count,
                    meetings_count=meetings_count,
                    cleanup_suggested_count=cleanup_suggested_count,
                    summary_markdown=summary_markdown,
                    stats_json=stats_json,
                )
                session.add(rec)
            else:
                rec.total_emails = total_emails
                rec.important_count = important_count
                rec.need_reply_count = need_reply_count
                rec.meetings_count = meetings_count
                rec.cleanup_suggested_count = cleanup_suggested_count
                rec.summary_markdown = summary_markdown
                rec.stats_json = stats_json
            session.commit()
            session.refresh(rec)
            return rec
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving daily digest: {e}")
            raise
        finally:
            session.close()

    def get_latest_daily_digest(self) -> Optional[DailyDigestRecord]:
        session = self.get_session()
        try:
            return session.query(DailyDigestRecord).order_by(desc(DailyDigestRecord.digest_date)).first()
        finally:
            session.close()


# Global repository instance
repository = Repository()
