"""APScheduler for periodic scrapes and prediction pipeline."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from backend.config import NEWS_SCRAPE_INTERVAL, STOCK_SCRAPE_INTERVAL, PREDICTION_INTERVAL
from backend.db import SessionLocal, init_db
from backend.scrapers import fetch_and_store_news, fetch_and_store_stocks
from backend.analysis import analyze_news_sentiment, compute_signals, store_signals

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_news_job():
    """Fetch news, run sentiment, and trigger prediction pipeline."""
    db = SessionLocal()
    try:
        fetch_and_store_news(db)
        analyze_news_sentiment(db)
    except Exception as e:
        logger.exception("News job failed: %s", e)
    finally:
        db.close()


def _run_stocks_job():
    """Fetch stocks and recompute signals."""
    db = SessionLocal()
    try:
        fetch_and_store_stocks(db)
        results = compute_signals(db)
        store_signals(db, results)
    except Exception as e:
        logger.exception("Stocks job failed: %s", e)
    finally:
        db.close()


def _run_prediction_job():
    """Run the prediction pipeline to generate forward-looking signals."""
    from backend.intelligence.predictor import run_prediction_pipeline
    db = SessionLocal()
    try:
        count = run_prediction_pipeline(db)
        if count:
            logger.info("Prediction pipeline: %d new predictions.", count)
    except Exception as e:
        logger.exception("Prediction job failed: %s", e)
    finally:
        db.close()


def start_scheduler():
    """Start periodic jobs."""
    init_db()
    scheduler.add_job(_run_news_job, "interval", seconds=NEWS_SCRAPE_INTERVAL, id="news")
    scheduler.add_job(_run_stocks_job, "interval", seconds=STOCK_SCRAPE_INTERVAL, id="stocks")
    scheduler.add_job(_run_prediction_job, "interval", seconds=PREDICTION_INTERVAL, id="predictions")
    scheduler.start()

    # Run startup jobs (news first, then predictions which depend on news)
    try:
        _run_news_job()
        _run_stocks_job()
        _run_prediction_job()
    except Exception as e:
        logger.warning("Startup scrape failed: %s", e)

    logger.info(
        "Scheduler started: news every %ds, stocks every %ds, predictions every %ds",
        NEWS_SCRAPE_INTERVAL, STOCK_SCRAPE_INTERVAL, PREDICTION_INTERVAL,
    )


def stop_scheduler():
    """Stop scheduler."""
    scheduler.shutdown(wait=False)
