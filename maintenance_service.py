from config import MAINTENANCEMODE, MAINTENANCEMESSAGE
from threading import Lock

class MaintenanceService:
    def init(self):
        self.maintenancemode = MAINTENANCE_MODE
        self._lock = Lock()

    def is_maintenance(self) -> bool:
        with self._lock:
            return self.maintenancemode

    def enable(self):
        with self._lock:
            self.maintenancemode = True

    def disable(self):
        with self._lock:
            self.maintenancemode = False

    def get_message(self) -> str:
        return MAINTENANCE_MESSAGE

maintenance_service = MaintenanceService()