import re
import sqlite3

from .database_actions import DatabaseActions

class SqliteDatabaseActions(DatabaseActions):
    def __init__(self, database_location):
        self.database_name = database_location
        self.connection = self._connect(database_location)

    def _connect(self, database_location):
        '''Overrides the base connect class with sqlite commands for local database functionality'''
        connection = None
        try:
            connection = sqlite3.connect(database_location)
        except Exception as e:
            raise ConnectionError(f"Unable to connect to database: {e}")
        return connection

    def set_database_map(self, table):
        '''simple setter that sets the database map
        Args:
            map: a dict of column headers'''
    
        query = """SELECT name FROM pragma_table_info(?);"""
        table_columns = self.execute_query(query, (table,))
        self.database_map = [column[0] for column in table_columns]

    def check_table_exists(self, table_name:str):
            '''checks to see if a table exists and returns a boolean value depending on the result
            Args:
                table_name: a string containing the name of the table
            '''
            query = """
                SELECT EXISTS (
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name = ?
                )
            """
    
            cursor = self.connection.cursor()
            try:
                cursor.execute(query, (table_name,))
                return bool(cursor.fetchone()[0])
            except sqlite3.Error as err:
                raise ConnectionError(f"Error: '{err}'") from err
            finally:
                cursor.close()

    def create_table(self, table_name:str, database_columns:dict):
        '''Creates a table within a given database
        Args:
            table_name: a string with the tables name
            database_columns: a database containing the headers used for the database columns
        '''
        query = "CREATE TABLE ? ("
        table_column_string = f"? ?,"
        table_details = []
        for column in database_columns:
            table_details.append(column, type(database_columns[column]))
            query += table_column_string
        query += ");"

        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (table_details))
        except sqlite3.Error as err:
            raise self.connection(f"Error creating table : {err}") from err
        finally:
            cursor.close()