import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

def get_db_session():
    """Create database session"""
    host = os.getenv('MYSQL_HOST')
    port = os.getenv('MYSQL_PORT_INTERNAL', '3306')
    database = os.getenv('MYSQL_DATABASE')
    user = os.getenv('MYSQL_USER')
    password = os.getenv('MYSQL_PASSWORD')

    try:
        port = int(port)
    except (TypeError, ValueError):
        logger.warning(f"Invalid port value: {port}, using default 3306")
        port = 3306

    if not all([host, database, user, password]):
        raise ValueError("Missing required database configuration")

    db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def save_or_update(session, model_class, record_id, data):
    """Save or update database record"""
    try:
        record = session.query(model_class).get(record_id)
        if not record:
            record = model_class(id=record_id)
            session.add(record)
        
        for key, value in data.items():
            setattr(record, key, value)
            
        return record
    except Exception as e:
        logger.error(f"Error saving {model_class.__name__} {record_id}: {str(e)}")
        raise
