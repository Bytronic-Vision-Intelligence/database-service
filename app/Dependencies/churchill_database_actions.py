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
        Returns:
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
        query = f"{table} ({columns}) VALUES ({placeholders})"
        parameters = tuple(data[field] for field in fields)
        return query, parameters

    def _map_from_database(self):
        pass

    def _construct_search_query(self, terms:dict, database_table:str):
        '''creates a search queory from a dictionary of terms
        Args:
            terms: a dictionary of terms to be used for the search'''
        fields = [item for item in terms if item not in {"command", "destination", "database_name"}]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_table):
            raise ValueError("Invalid database table name")
        if not fields:
            raise ValueError("No data fields supplied")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) for field in fields):
            raise ValueError("Invalid database column name")

        columns = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        query = f"{database_table} FROM {columns} WHERE RegNum LIKE '{placeholders}%'"
        parameters = tuple(terms[field] for field in fields)
        return query, parameters

    def add_sku(self,database_table, sku:dict):
        '''Adds a new sku to the churchill database.

        Args:
            sku: a dictionary containing the sku data in the following format: depth image: binary, colour image: binary, depth: float, area: float, diameter: float
        '''
        query, parameters = self._map_to_database(sku, table=database_table)
        self.execute_query(f"INSERT INTO {query}", parameters)

    def fuzzy_search(self, database_table, search_details:dict):
        '''Performs a fuzzy search on a database table based on a set list of comumns and their associated data
        Args:
            database_table: a string value containing the database table that will be targeted for the search
            search_details: a ditcionary containing the search details
        Returns:
            search_results: a dictionary of results from the server
        '''

        search_term, parameters = self._construct_search_query(search_details, database_table)
        query = f"SELECT {search_term} ORDER BY RegNum"
        self.execute_query(query, parameters)
