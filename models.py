import os

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

MYSQL_ROOT_PASSWORD = os.getenv('MYSQL_ROOT_PASSWORD')
DB_NAME = os.getenv('MYSQL_DATABASE')

DATABASE_URL = f'mysql+pymysql://root:{MYSQL_ROOT_PASSWORD}@db:3306/{DB_NAME}'
Base = declarative_base()


class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)
    url = Column(String(255))
    channel_id = Column(String(255))

    alerts = relationship('Alert', back_populates='department')


class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    department_name = Column(String(255), ForeignKey('departments.name'))
    link = Column(String(511), unique=True)
    scraped_at = Column(TIMESTAMP, default=datetime.now())
    sent_at = Column(TIMESTAMP, nullable=True)
    status = Column(String(255), default='pending')

    department = relationship('Department', back_populates='alerts')


def get_session():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    return session()
