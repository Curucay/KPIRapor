import os
from dotenv import load_dotenv

class Settings:
    def __init__(self):
        self.ENV_PATH = os.getenv(
            "ENV_PATH",
            r"C:\Users\celal.urucay\OneDrive - Erkurt Holding\Desktop\Erkurt Python Calismalar\KPIRapor\.env"
        )
        load_dotenv(self.ENV_PATH)
        self.DB_CONN_STR = os.getenv("DB_CONN_STR")

        # Oracle Connection
        self.ORACLE_HOST = os.getenv("ORACLE_HOST")
        self.ORACLE_PORT = os.getenv("ORACLE_PORT")
        self.ORACLE_SERVICE = os.getenv("ORACLE_SERVICE")
        self.ORACLE_USER = os.getenv("ORACLE_USER")
        self.ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
        self.ORACLE_CONNECT_AS = os.getenv("ORACLE_CONNECT_AS")


        # Page config
        self.PAGE_TITLE = "Formfleks A.Ş. - Raporlama Sistemi"
        self.PAGE_ICON = r"C:\Users\celal.urucay\OneDrive - Erkurt Holding\Desktop\Erkurt Python Calismalar\HizliRapor\assets\Formfleks_Icon.png"
        self.LAYOUT = "wide"


settings = Settings()