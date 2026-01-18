import datetime
import motor.motor_asyncio
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.passwords = self.db.passwords

    def new_user(self, id):
        return dict(
            id=id,
            join_date=datetime.date.today().isoformat(),
            last_activity=datetime.datetime.now().isoformat()
        )

    async def add_user(self, id):
        user = self.new_user(id)
        await self.col.insert_one(user)
        
    async def add_user_pass(self, id, ag_pass):
        await self.add_user(int(id))
        await self.col.update_one({'id': int(id)}, {'$set': {'ag_p': ag_pass}})
    
    async def get_user_pass(self, id):
        user_pass = await self.col.find_one({'id': int(id)})
        return user_pass.get("ag_p", None) if user_pass else None
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id': int(id)})
        return True if user else False

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})
    
    async def update_user_activity(self, user_id):
        """Actualiza la última actividad del usuario"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'last_activity': datetime.datetime.now().isoformat()}}
        )
    
    async def get_active_users_count(self, days=7):
        """Obtiene usuarios activos en los últimos X días"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        count = await self.col.count_documents({
            'last_activity': {'$gte': cutoff_date.isoformat()}
        })
        return count

# Instancia global
from config import DATABASE_URL, DB_NAME
db = Database(DATABASE_URL, DB_NAME)