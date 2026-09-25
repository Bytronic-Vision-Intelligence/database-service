from logging import info
from abc import ABC, abstractmethod
import uuid

class DatabaseActions(ABC):
    '''a base class containing database connections and actions
    Parameters:
        host: the host address of the server
        user: the username for server connection
        password: the password for server connection
        database_name: the name of the target database
    '''
    @abstractmethod
    def __init__():
        pass

    @abstractmethod
    def set_database_map(self, table):
        pass

    @abstractmethod
    def _connect(self):
        pass
    
    @abstractmethod
    def _map_to_database(self, query):
        pass

    @abstractmethod
    def _map_from_database(self, result, map, headers):
        pass

    def execute_query(self, query, parameters=None):
        '''executes a queory to the connected server and database
        Args:
            query: a string containing a valid sql query
        '''
        if query is None or query == "":
            raise ValueError("query cannot be empty")
        
        cursor = self.connection.cursor()
        print(f"Info : Executing queory: {query}")
        try:
            if type(parameters) == str: parameters = (parameters,)
            cursor.execute(query, parameters)
            self.connection.commit()
            print("Query successful")
            return cursor.fetchall()
        except Exception as err:
            raise ConnectionError(f"Error: execute_query '{err}'")

    def _disconnect(self):
        '''disconnects from the current database/server'''
        if not self.connection is None:
            self.connection.disconnect()

    def add_sku(self,database_table, sku:dict, headers:list):
            '''Adds a new sku to a database table.
            Args:
                sku: a dictionary containing the sku data in the following format: depth image: binary, colour image: binary, depth: float, area: float, diameter: float
            '''
            query, parameters = self._map_to_database(sku, database_table, headers)
            print("Info : database actions - data mapped")
            self.execute_query(f"INSERT INTO {query}", parameters)
    
    def search(
            self, 
            database_table:str, 
            search_details:dict,
            headers:list,
            threshold:float = 0):
        '''Performs a search on a database table based on a set list of comumns and their associated data
        Args:
            database_table: a string value containing the database table that will be targeted for the search
            search_details: a ditcionary containing the search details
        Returns:
            search_results: a dictionary of results from the server
        '''
        if threshold == 0:
            search_term, parameters = self._construct_search_query(search_details, database_table, headers)
        else:
            search_term, parameters = self._construct_fuzzy_search_query(search_details, database_table, threshold, headers)
        query = f"{search_term}"

        results = self.execute_query(query, parameters)
        try:
            results = self._map_from_database(results, self.database_map)
        except Exception as e:
            print(f"Error: unable to map data from database: {e}")
            info(f"Error: unable to map data from database: {e}")
        return results

    def check_duplicate(self, header:str, data_entry:any, table:str):
        '''searches the database using a given header and data entry to 
        determine if it already exists in the database
        Args:
            header: the header to search as a string
            data_entry: the data to find in the database
            table: the table to search
        Returns:
            a boolean result
        '''
        search_term, parameters = self._search_single_column(header,data_entry, table)
        query = f"{search_term}"
        results = self.execute_query(query, parameters)
        if len(results)>0:return True
        return False


    def _generate_uid(self):
            '''returns a unique identifier'''
            uid = str(uuid.uuid4())
            print(f"Info : UID generated {uid}")
            return uid