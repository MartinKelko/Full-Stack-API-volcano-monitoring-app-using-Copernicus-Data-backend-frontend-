from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    sh_client_id: str = os.getenv("SH_CLIENT_ID", "")
    sh_client_secret: str = os.getenv("SH_CLIENT_SECRET", "")
    sh_token_url: str = os.getenv(
        "SH_TOKEN_URL",
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    sh_base_url: str = os.getenv("SH_BASE_URL", "https://sh.dataspace.copernicus.eu")
    output_dir: str = os.getenv("OUTPUT_DIR", "output")

settings = Settings()