from pathlib import Path
import sys
import cv2 as cv

p=Path(__file__).parents[2]

if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from .database_actions import database_actions

class churchill_database_actions(database_actions):
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

        columns = ""
        contents = ""

        for item in data:
            columns += f"{item},"
            contents += f"{data[f'{item}']},"

        query = f"INSERT INTO {table} ({columns}) VALUES ({contents})"
        query=query.replace(",)", ")")
        return query

    def _map_from_database(self):
        pass

    def add_sku(self,database_table, sku:dict):
        '''adds a new sku to the churchill database.

        Args:
            sku: a dictionary containing the sku data in the following format: depth image: binary, colour image: binary, depth: float, area: float, diameter: float
        '''

        print(f"adding data string {sku} to {self.database_name}")

        pop_new_sku = self._map_to_database(sku, table=database_table)

        self.execute_query(pop_new_sku)

if __name__ == "__main__":
    database_table = "sku_table"
    db = churchill_database_actions(password="root", database_name="churchill_database")

    depth_image = cv.imread("C:/Users/AmyHarrison/inference-methods/images/3d/churchill/imageNew.png").tobytes()
    colour_image = cv.imread("C:/Users/AmyHarrison/inference-methods/images/3d/churchill/cam0_ljs_20260722_120658.png").tobytes()

    new_sku = {
        "depth":10, "area":10, "perimeter":10
    }

    print(new_sku)
    db.add_sku(database_table, new_sku)