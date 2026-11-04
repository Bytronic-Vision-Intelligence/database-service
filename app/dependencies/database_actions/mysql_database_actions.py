from logging import info
import mysql.connector
from mysql.connector import Error
from .database_actions import DatabaseActions

class MysqlDatabaseActions(DatabaseActions):
    '''MySQL backend. NOT USABLE YET: it will be fixed during the database-service rework.

    As it stands:
    - it cannot be created: set_database_map, _map_to_database, _map_from_database and
      _map_remove_row are not implemented, so Python refuses to instantiate the class;
    - create_db_connection calls self._disconnect, which does not exist;
    - it has none of the search query builders SqliteDatabaseActions has;
    - nothing in the config selects it: DatabaseStateMachine always uses SQLite.
    '''
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
                info("MySQL Database connection successful")
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
            info("MySQL Database connection successful")
        except Error as err:
            raise ConnectionError(f"Error: '{err}'") 
