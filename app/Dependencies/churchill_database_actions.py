import re

from .database_actions import DatabaseActions

class ChurchillDatabaseActions(DatabaseActions):
    '''a class to hold the specific functions for the churchill process flow inherits from database_actions.

    Overrides:
        _map_tp_database: updated with database map to convert dictionary data to sql format
        '''

    def _map_to_database(self, data:dict[str, any], table):
        '''converts a dictionary into a valid format to be sent to an sql server based on the database structure. 

        Args: 
            data: a dictionary containing the comumn name as key and the data as data
        Returns
            query: a string formatted correctly as an sql request
        '''

        fields = [item for item in data if item not in {"command", "destination", "database_name"}]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError("Invalid database table name")
        if not fields:
            raise ValueError("No data fields supplied")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) for field in fields):
            raise ValueError("Invalid database column name")

        columns = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        parameters = tuple(data[field] for field in fields)
        return query, parameters

    def _map_from_database(self):
        pass

    def add_sku(self,database_table, sku:dict):
        '''Adds a new sku to the churchill database.

        Args:
            sku: a dictionary containing the sku data in the following format: depth image: binary, colour image: binary, depth: float, area: float, diameter: float
        '''

        print(f"adding data string {sku} to {self.database_name}")

        query, parameters = self._map_to_database(sku, table=database_table)
        self.execute_query(query, parameters)

    def search_database(self,database_table, item_details:dict) -> dict:
        '''searches the database table for all items matching the details given and returns all fuzzy matching items
        
        Args:
            database_table: a string containing the name of the database table to be searched
            item_details: a dictionary containing the details of the item being searched for containing the depth:float, area:float, perimeter:float
        
        Returns:
            search_results: a dictionary of results'''
        pass