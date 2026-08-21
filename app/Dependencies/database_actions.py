import mysql.connector
from mysql.connector import Error
from abc import ABC, abstractmethod

class DatabaseActions(ABC):
    '''a class containing database connections and actions
    Parameters:
        host: the host address of the server
        user: the username for server connection
        password: the password for server connection
        database_name: the name of the target database
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
            print("MySQL Database connection successful")
        except Error as err:
            raise ConnectionError(f"Error: '{err}'")

        return connection
    
    @abstractmethod
    def _map_to_database(self, query):
        pass

    @abstractmethod
    def _map_from_database(self, result):
        pass

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

    def execute_query(self, query, parameters=None):
        '''executes a queory to the connected server and database
        Args:
            query: a string containing a valid sql query
        '''
        if query is None or query == "":
            raise ValueError("query cannot be empty")
        
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, parameters)
            self.connection.commit()
            print("Query successful")
        except Error as err:
            raise ConnectionError(f"Error: '{err}'")

    def _disconnect(self):
        '''disconnects from the current database/server'''
        if not self.connection is None:
            self.connection.disconnect()