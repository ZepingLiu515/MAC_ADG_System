from database.connection import init_db, engine
from database.models import Base

print("--- Force Initializing Database ---")

# 1. Drop all existing tables (Clean Slate)
try:
    Base.metadata.drop_all(bind=engine)
    print("Dropped old tables.")
except Exception as e:
    print(f"Warning dropping tables: {e}")

# 2. Create tables fresh
try:
    init_db()
    print("✅ SUCCESS: Database tables created successfully!")
    print("You can now run 'streamlit run main.py'")
except Exception as e:
    print(f"❌ ERROR: Could not create tables. Reason: {e}")