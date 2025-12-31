from config import MAXUSERQUOTA, MAXUSERQUOTAMB, USERQUOTAWARNINGPERCENT
from fileservice import fileservice

class QuotaService:
    def init(self):
        self.maxquotabytes = MAXUSERQUOTA
        self.maxquotamb = MAXUSERQUOTA_MB
        self.warningpercent = USERQUOTAWARNINGPERCENT

    def getuserusage(self, user_id: int):
        usedbytes = fileservice.getuserstorageusage(userid)
        usedmb = usedbytes / (1024 * 1024)
        percent = (usedbytes / self.maxquotabytes * 100) if self.maxquota_bytes > 0 else 0
        return usedbytes, usedmb, percent

    def canstore(self, userid: int, incoming_size: int):
        usedbytes, , percent = self.getuserusage(user_id)
        projected = usedbytes + incomingsize
        if projected > self.maxquotabytes:
            return False, (
                f"❌ Límite de almacenamiento alcanzado\n\n"
                f"Tu espacio asignado es de {self.maxquotamb} MB.\n"
                f"Actualmente estás usando {used_bytes / (1024 * 1024):.2f} MB.\n\n"
                f"Por favor, elimina algunos archivos con /cd downloads, /list y /delete <número>."
            )
        warning = None
        if percent >= self.warning_percent:
            warning = (
                f"⚠️ Aviso de espacio\n\n"
                f"Estás usando {percent:.1f}% de tu cuota ({usedbytes / (1024 * 1024):.2f} MB / {self.maxquota_mb} MB)."
            )
        return True, warning

quota_service = QuotaService()