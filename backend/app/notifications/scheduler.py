from apscheduler.schedulers.background import BackgroundScheduler
from app.core.logging import get_logger
from app.models.database import SessionLocal
from app.orchestrator.orchestrator import Orchestrator
from app.repositories.base import EntityDoc

logger = get_logger("scheduler")
scheduler: BackgroundScheduler = BackgroundScheduler()


def check_trips_job():
    logger.info("Executing scheduled periodic condition check on active trips")
    db = SessionLocal()
    try:
        trips_col = db.trips
        active_docs = list(trips_col.find({"status": "active"}))
        for doc in active_docs:
            trip_id = str(doc.get("_id", ""))
            try:
                events, replan_it = Orchestrator.check_conditions_and_replan(db, trip_id)
                if events:
                    logger.info(f"Scheduled check detected {len(events)} events for Trip {trip_id}")
            except Exception as e:
                logger.warning(f"Error checking conditions for Trip {trip_id}: {e}")
    except Exception as e:
        logger.warning(f"Error querying active trips in scheduler: {e}")


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(check_trips_job, "interval", minutes=60, id="periodic_condition_check", replace_existing=True)
        scheduler.start()
        logger.info("In-process APScheduler started (interval: 60 minutes)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped")
