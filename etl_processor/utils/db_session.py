# db_session.py

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Optional

logger = logging.getLogger(__name__)

def _resolve_env_var(value: str) -> str:
    """Resolve environment variable references in config values"""
    if not isinstance(value, str):
        return value
        
    if value.startswith("${") and value.endswith("}"):
        # Extract env var name and default value if provided
        env_var = value[2:-1]
        if ":-" in env_var:
            env_name, default = env_var.split(":-", 1)
            return os.getenv(env_name, default)
        return os.getenv(env_var, "")
    return value

def get_db_session(import_type: Optional[str] = None, config_loader = None):
    """Create database session with import-specific configuration"""
    try:
        # Get database config from import type if provided
        if import_type and config_loader:
            import_config = config_loader.get_import_config(import_type)
            db_config = import_config.get('database', {})
            
            # Resolve any environment variable references
            host = _resolve_env_var(db_config.get('host', os.getenv('MYSQL_HOST')))
            port = _resolve_env_var(db_config.get('port', os.getenv('MYSQL_PORT_INTERNAL', '3306')))
            database = _resolve_env_var(db_config.get('name', os.getenv('MYSQL_DATABASE')))
            user = _resolve_env_var(db_config.get('user', os.getenv('MYSQL_USER')))
            password = _resolve_env_var(db_config.get('password', os.getenv('MYSQL_PASSWORD')))
        else:
            # Fallback to environment variables
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
            missing = [var for var, val in {
                'host': host,
                'database': database,
                'user': user,
                'password': password
            }.items() if not val]
            raise ValueError(f"Missing required database configuration: {', '.join(missing)}")

        db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
        logger.debug(f"Creating database connection to {host}:{port}/{database} as {user}")
        
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        return Session()

    except Exception as e:
        logger.error(f"Error creating database session: {str(e)}")
        raise

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