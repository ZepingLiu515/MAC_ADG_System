from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

# 1. Define Base
Base = declarative_base()

# 2. Define Table Structures

class Faculty(Base):
    """
    [Table: Faculty List]
    Standard reference table for Judge Agent identity matching.
    支持多个部门/单位
    """
    __tablename__ = 'faculty'

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, unique=True, index=True, comment="Employee ID")
    name_zh = Column(String, nullable=False, comment="Chinese Name")
    # Store English variants, e.g., ["Zeping Liu", "Z.P. Liu"]
    name_en_list = Column(JSON, comment="List of English Name Variants") 
    # 向后兼容的单个部门字段
    department = Column(String, comment="Primary Department/School")
    # V2.0: 支持多个部门/单位，JSON 列表，例如 ["West China School of Medicine, Sichuan University", "College of Computer Science, Sichuan University"]
    departments = Column(JSON, comment="List of Departments/Schools")
    
    # Relationships
    matched_records = relationship("PaperAuthor", back_populates="matched_faculty")

class Paper(Base):
    """
    [Table: Papers]
    Stores basic metadata of papers.
    """
    __tablename__ = 'papers'

    doi = Column(String, primary_key=True, comment="DOI as Unique ID")
    title = Column(Text, comment="Paper Title")
    journal = Column(String, comment="Journal Name")
    publish_date = Column(String, comment="Publication Date")
    
    pdf_path = Column(String, comment="Local PDF File Path")
    # Status: PENDING / PROCESSING / COMPLETED / ERROR
    status = Column(String, default="PENDING", comment="Processing Status")
    
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    authors = relationship("PaperAuthor", back_populates="paper", cascade="all, delete-orphan")

class PaperAuthor(Base):
    """
    [Table: Paper Authors]
    Core data source for contribution analysis.
    支持多个单位
    """
    __tablename__ = 'paper_authors'

    id = Column(Integer, primary_key=True)
    paper_doi = Column(String, ForeignKey('papers.doi'))
    
    rank = Column(Integer, nullable=False, comment="Author Rank (1, 2, ...)")
    raw_name = Column(String, comment="Raw Name on Paper")
    # 向后兼容的单个单位字段
    raw_affiliation = Column(Text, comment="Raw Affiliation on Paper")
    # V2.0: 支持多个单位，JSON 列表
    raw_affiliations = Column(JSON, comment="List of Raw Affiliations on Paper")
    
    # Key Contribution Flags (Identified by Vision Agent)
    is_corresponding = Column(Boolean, default=False, comment="Is Corresponding Author")
    is_co_first = Column(Boolean, default=False, comment="Is Co-First Author")
    
    # Identity Matching (Decided by Judge Agent)
    matched_faculty_id = Column(Integer, ForeignKey('faculty.id'), nullable=True)
    # Enhanced matching metadata
    confidence_score = Column(Integer, default=0, comment="Matching confidence (0-100)")
    matched_level = Column(String, default="L1", comment="Matching level used: L1/L2/L3")
    match_signals = Column(JSON, nullable=True, comment="Debug signals: {name, aff, coauthor}")
    
    # Relationships
    paper = relationship("Paper", back_populates="authors")
    matched_faculty = relationship("Faculty", back_populates="matched_records")


class CorrectionMemory(Base):
    """
    [Table: Correction Memory]
    Minimal RAG-style memory for storing manual correction samples.
    """
    __tablename__ = 'correction_memory'

    id = Column(Integer, primary_key=True)
    doi = Column(String, nullable=True, comment="Related DOI (optional)")
    layout_fingerprint = Column(JSON, comment="Token list or layout fingerprint")
    error_type = Column(String, comment="Error category")
    correction = Column(JSON, comment="Correction payload (structured)")
    source = Column(String, comment="Source of correction (manual/import)")
    notes = Column(Text, comment="Free-form notes")
    created_at = Column(DateTime, default=datetime.now)


class SystemSetting(Base):
    """[Table: System Settings]
    Stores global configuration values (key/value).
    """

    __tablename__ = 'system_settings'

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# 3. Database Initialization Logic

def init_db(db_name="mac_adg.db"):
    """
    Initialize database file and create all tables.
    """
    # Ensure data directory exists
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    db_path = os.path.join(data_dir, db_name)
    sqlite_url = f"sqlite:///{db_path}"
    
    engine = create_engine(sqlite_url, echo=False)
    
    # Create Tables
    Base.metadata.create_all(engine)
    print(f"[INFO] Database initialized at: {db_path}")
    
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)