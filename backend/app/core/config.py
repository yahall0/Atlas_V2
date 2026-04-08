import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://atlas:atlaspass@db:5432/atlas_db")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")
