import mysql.connector
from logging import info
from mysql.connector import Error
from abc import ABC, abstractmethod
class DatabaseActions(ABC):
    '''a class containing database connections and actions using mysql as the native framework for database connections
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

    @abstractmethod
    def set_database_map(self, table):
        pass

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
    def _map_from_database(self, result, map):
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
            return cursor.fetchall()
        except Error as err:
            raise ConnectionError(f"Error: '{err}'")

    def _disconnect(self):
        '''disconnects from the current database/server'''
        if not self.connection is None:
            self.connection.disconnect()

    def add_sku(self,database_table, sku:dict):
            '''Adds a new sku to a database table.
            Args:
                sku: a dictionary containing the sku data in the following format: depth image: binary, colour image: binary, depth: float, area: float, diameter: float
            '''
            query, parameters = self._map_to_database(sku, table=database_table)
            self.execute_query(f"INSERT INTO {query}", parameters)
    
    def search(self, database_table:str, search_details:dict, threshold:float = 0):
        '''Performs a search on a database table based on a set list of comumns and their associated data
        Args:
            database_table: a string value containing the database table that will be targeted for the search
            search_details: a ditcionary containing the search details
        Returns:
            search_results: a dictionary of results from the server
        '''
        if threshold == 0:
            search_term, parameters = self._construct_search_query(search_details, database_table)
        else:
            search_term, parameters = self._construct_fuzzy_search_query(search_details, database_table, threshold)
        query = f"{search_term}"
        results = self.execute_query(query, parameters)
        try:
            results = self._map_from_database(results, self.database_map)
        except Exception as e:
            print(f"Error: unable to map data from database: {e}")
            info(f"Error: unable to map data from database: {e}")
        return results