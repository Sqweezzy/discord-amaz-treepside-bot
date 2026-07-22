import os
from decouple import config
from sqlalchemy import text, create_engine


engine = create_engine(config('DB_URL'), echo=True)
class Database_use:
    
    def execute_query(self, query: str):
        with engine.connect() as conn:
            try:
                conn.execute(text(query))
                conn.commit()
            except Exception as e:
                print(f"ОШИБКА !!!!!!! !! !! !!!!\n {str(e)}")
                
    def get_last_id(self):
        with engine.connect() as conn:
            try:
                query = 'select post_id from post_inf order by id desc limit 1'
                res = conn.execute(text(query))
                return res.scalar_one_or_none()
            except Exception as e:
                print(f"ОШИБКА получения last_id\n {str(e)}")
                return None

    def save_last_id(self, last_id):
        with engine.connect() as conn:
            try:
                query = text('insert into post_inf (post_id) values (:last_id)')
                conn.execute(query, {"last_id": last_id})
                conn.commit()
            except Exception as e:
                print(f"ОШИБКА инсерт\n {str(e)}")
    
    def create_models(self):
        with engine.connect() as conn:
            try:
                conn.execute(text("""
                                create table if not exists post_inf (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                           post_id varchar(255))
                                """))
                conn.commit()
            except Exception as e:
                print(f"ОШИБКА !!!!!!! !! !! !!!!\n {str(e)}")
            
    def drop_models(self):
        with engine.connect() as conn:
            try:
                conn.execute(text('DROP TABLE IF EXISTS post_inf'))
            except Exception as e:
                print(f"ОШИБКА !!!!!!! !! !! !!!!\n {str(e)}")
                
database = Database_use()

if __name__ == '__main__':
    
    print(database.get_last_id())
    
    # database.create_models()
