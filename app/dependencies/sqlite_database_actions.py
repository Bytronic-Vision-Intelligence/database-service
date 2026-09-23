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

    def _construct_search_query(
            self, 
            terms:dict, 
            database_table:str,
            headers:list
        ):
        '''creates a search queory from a dictionary of terms
        Args:
            terms: a dictionary of terms to be used for the search
        Returns:
            query: a string containing the correctly formatted queory
            parameters: a list of parameters
        '''
        
        fields = headers
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_table):
            raise ValueError("Invalid database table name")
        if not fields:
            raise ValueError("No data fields supplied")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) for field in fields):
            raise ValueError("Invalid database column name")

        columns = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        query = f"SELECT * FROM {database_table} WHERE ({columns}) = ({placeholders});"
        parameters = tuple(terms[field] for field in fields)
        return query, parameters

    def _construct_fuzzy_search_query(
            self, 
            terms:dict, 
            database_table:str, 
            threshold:int, 
            headers:list
        ):
        '''creates a search queory from a dictionary of terms
        Args:
            terms: a dictionary of terms to be used for the search'''
        
        fields = headers
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_table):
            raise ValueError("Invalid database table name")
        if not fields:
            raise ValueError("No data fields supplied")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) for field in fields):
            raise ValueError("Invalid database column name")

        if threshold < 0:
            raise ValueError("Threshold must be non-negative")

        conditions = [
            f"ABS({field} - ?) <= ?"
            for field in fields
        ]

        query = f"""
            SELECT *
            FROM {database_table}
            WHERE {" AND ".join(conditions)}
        """.strip()

        parameters = tuple(
            value
            for field in fields
            for value in (terms[field], threshold)
        )

        return query, parameters

    def _construct_update_query(
            self,
            values:dict,
            database_table:str,
            row_id,
            editable:list
        ):
        '''Builds an UPDATE touching one row and only the editable columns.

        Column names cannot be bound as parameters -- they are interpolated
        into the statement -- so each one is checked against the identifier
        pattern AND against the list config permits, before it reaches the
        string. The values themselves are always bound.
        Args:
            values: a dictionary of column name to new value
            database_table: the table holding the row
            row_id: the id of the row to change
            editable: the columns config permits changing
        Returns:
            query: a string formatted correctly as an sql statement
            parameters: a tuple of values to bind, row id last
        '''
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database_table):
            raise ValueError("Invalid database table name")
        if not values:
            raise ValueError("No data fields supplied")
        if str(row_id or "").strip() == "":
            raise ValueError("A row id is required")
        if not editable:
            raise ValueError("No editable columns configured")

        fields = list(values)
        for field in fields:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
                raise ValueError("Invalid database column name")
            if field not in editable:
                raise ValueError(f"Column '{field}' is not editable")

        assignments = ", ".join(f"{field} = ?" for field in fields)
        # `id` rather than the table's literal `Id`: sqlite matches column
        # names without regard to case, and every table here names its key
        # this way, so the statement reads the same as the rest of the service.
        query = f"UPDATE {database_table} SET {assignments} WHERE id = ?;"
        parameters = tuple(values[field] for field in fields) + (row_id,)
        return query, parameters

    def create_table(self, table_name:str, database_columns:dict):
        '''Creates a table within a given database - non functioning, add chore to fix this
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

    def _map_to_database(self, data:dict[str, any], table, include_headers:dict):
        '''converts a dictionary into a valid format to be sent to an sql server based on the database structure
        Args:
            data: a dictionary containing the comumn name as key and the data as data
        Returns:
            query: a string formatted correctly as an sql request
        '''

        data["id"] = self._generate_uid()
        
        fields =include_headers
        print(f"Info : Headers: {fields}")

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError("Invalid database table name")
        if not fields:
            raise ValueError("No data fields supplied")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) for field in fields):
            raise ValueError("Invalid database column name")

        columns = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        query = f"{table} ({columns}) VALUES ({placeholders})"
        parameters = ()
        for field in fields:
            try:
                print(f"added data to parameters {field} {data[field]}")
                parameters += (data[field],)
            except:
                print(f"could not add data to parameters {data[field]}")
                parameters += ("None",)
                
        print("Info : data- mapped")
        return query, parameters
    
    def _map_from_database(self, results, table_columns):
        '''Converts the database output to a dictionary based on the database keys
        Args:
            result: the result of the database queory
            table_columns: a dictionary of columns found in the database
        Returns:
            mapped_result: a dictionary of results, appropriately mapped to the correct columns
        '''
        mapped_result = {}

        for row_id, result in enumerate(results):
            mapped_result[row_id] = {}

            for column, value in zip(table_columns, result):
                mapped_result[row_id][column] = value

        return mapped_result