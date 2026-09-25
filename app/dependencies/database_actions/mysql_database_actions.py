import mysql.connector
from mysql.connector import Error
from .database_actions import DatabaseActions

class MysqlDatabaseActions(DatabaseActions):
    def __init__(
        self,host:str="127.0.0.1",
        user:str="root",
        password:str="",
        database_name:str=""
    ):

        self.host = host
        self.user = user
        self.password = password
        self.database_name = database_name

        self.connection = self._connect()
        self.create_db_connection()

    def _connect(self):
            '''creates a connection to an sql server'''
            connection = None
            try:
                connection = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    passwd=self.password
                )
                print("MySQL Database connection successful")
            except Error as err:
                raise ConnectionError(f"Error: '{err}'")
    
            return connection

    def create_db_connection(self):
        '''creates a connection to a database on the connected server'''
        self._disconnect()
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                passwd=self.password,
                database=self.database_name
            )
            print("MySQL Database connection successful")
        except Error as err:
            raise ConnectionError(f"Error: '{err}'") 