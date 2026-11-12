from db.database import db
from sqlalchemy import Column, Integer, String, DateTime, Text


class User(db.Model):
    __tablename__ = "openldr_api_user_users"
    __bind_key__ = "users"  # Specify the bind key for the users database
    id = Column(Integer, autoincrement=True, unique=True, primary_key=True)
    user_id = Column(
        String(250), nullable=False, unique=True
    )  # Unique identifier for the user
    user_name = Column(String(250), nullable=False)
    first_name = Column(String(250), nullable=False)
    last_name = Column(String(250), nullable=False)
    password = Column(String(250), nullable=False)
    start_date = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    role = Column(String(50), nullable=False)  # One canonical role from auth.roles.
    email = Column(String(250), nullable=True)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"User(user_id={self.user_id}, user_name={self.user_name}, role={self.role}, email={self.email})"


class UserLogs(db.Model):
    __tablename__ = "openldr_api_user_logs"
    __bind_key__ = "users"  # Specify the bind key for the users database
    id = Column(Integer, autoincrement=True, unique=True, primary_key=True)
    user_id = Column(String(250), nullable=False, unique=False)
    log_id = Column(String(250), nullable=False, unique=True)
    log_date = Column(DateTime, nullable=False)
    log_type = Column(String(50), nullable=False)  # e.g., 'login', 'logout', etc.
    log_details = Column(Text, nullable=False)

    def __repr__(self):
        return f"UserLogs(user_id={self.user_id}, log_id={self.log_id}, log_date={self.log_date}, log_type={self.log_type}, log_details={self.log_details})"
