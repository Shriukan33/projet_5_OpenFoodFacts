import requests
import mysql.connector
from mysql.connector import Error, DatabaseError
from settings_local import ROOT_PASSWORD, DB_NAME, CATEGORIES


class SetupDatabase:

    def __init__(self):
        database_already_exists = self.check_database_existence(DB_NAME)

        if not database_already_exists:
            json_data = self.get_json_data_from_api()

            self.create_database_if_doesnt_exist()
            self.create_tables()

            data = self.request_to_data(json_data)
            self.insert_data_into_table("category", CATEGORIES)
            self.insert_data_into_table("product", data)

    def check_database_existence(self, DB_NAME: str) -> bool:
        """
        Checks if database exists in MySQL.
        Returns True if the database exists.
        DB_NAME is the value of the constant stored in settings_local.py
        """
        try:
            sql = mysql.connector.connect(host="localhost",
                                          user="root",
                                          password=ROOT_PASSWORD,
                                          database="mysql")

            cursor = sql.cursor()
            cursor.execute("SHOW DATABASES;")
            result = cursor.fetchall()
            for database in result:
                if database[0] == DB_NAME:
                    return True

            return False

        except Error as e:
            print("Erreur de connexion à MySQL", e)

        finally:
            if sql.is_connected():
                cursor.close()
                sql.close()

    def get_json_data_from_api(self) -> dict:
        print("Récupération de données depuis OpenFoodFacts...")
        url = "https://fr.openfoodfacts.org/cgi/search.pl?json=true&action=process&sort_by=popularity&page_size=500&page=1&sort_by=unique_scans_n&fields=product_name,nutriscore_grade,url,stores,purchase_places,pnns_groups_1,pnns_groups_2&coutries=france"  # noqa
        headers = {"User-Agent": "Projet5 - Linux/ubuntu - Version 1.0"}
        r = requests.get(url, headers=headers)

        # Turn json response into a dict.
        json_data = r.json()
        print("Données collectées avec succès !")
        return json_data

    def create_database_if_doesnt_exist(self):
        """Connects to mysql thanks to config file and create
            a database if it doesn't already exist"""

        try:
            sql = mysql.connector.connect(host="localhost",
                                          user="root",
                                          password=ROOT_PASSWORD,
                                          database="mysql")
            print("Connecté à MySQL !\n")
            cursor = sql.cursor()
            sql_create_db_query = (
                """CREATE DATABASE IF NOT EXISTS {} DEFAULT CHARACTER SET 'utf8mb4';""".format(DB_NAME))  # noqa
            print("Creation de '{}' ...\nTerminée !".format(DB_NAME))
            cursor.execute(sql_create_db_query)

        except Error as e:
            print("Erreur de connexion à MySQL", e)

        except DatabaseError as e:
            print("Erreur lors de la création de la base de données", e)

        finally:
            if sql.is_connected():
                cursor.close()
                sql.close()

    def create_tables(self) -> None:
        """Creates tables for the OpenFoodFacts database."""

        # Descriptions of the tables
        tables = {}
        # category must be created first because it's used as foreign key.
        tables["category"] = """CREATE TABLE IF NOT EXISTS category (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255)
            );"""

        # product table uses the foreign key of category
        # First item of category is id 1, the 2nd is id 2, etc.
        tables["product"] = """CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            product_name TEXT,
            nutriscore_grade TEXT,
            url TEXT,
            stores TEXT,
            purchase_places TEXT,
            pnns_groups_1 TEXT,
            pnns_groups_2 INTEGER,
            FOREIGN KEY (pnns_groups_2) REFERENCES category (id)
        );"""

        tables["saved"] = """CREATE TABLE IF NOT EXISTS saved (
            id INTEGER UNIQUE,
            CONSTRAINT fk_product_id
                FOREIGN KEY id(id)
                REFERENCES product (id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
            );"""

        print("Création des tables dans la base de donnée...")
        try:
            sql = mysql.connector.connect(host="localhost",
                                          user="root",
                                          password=ROOT_PASSWORD,
                                          database=DB_NAME)

            cursor = sql.cursor()
            for name, ddl in tables.items():
                cursor.execute(ddl)
                print("Table", name, " créée avec succès !")

            print("Tables créées avec succès !")
        except Error as e:
            print(f"Erreur lors de la création de {name} :", e)

        except DatabaseError as e:
            print("Erreur lors de la création de la base de données", e)

        finally:
            if sql.is_connected():
                cursor.close()
                sql.close()

    def match_category_with_id(self, category_name: str) -> int:
        """
        Returns the ID corresponding to a given category name.
        ID corresponds to the id field in category table.
        """
        cat_to_id = {}
        for index, category in enumerate(CATEGORIES):
            cat_to_id[category] = index+1
        try:
            id = int(cat_to_id[category_name])
        except KeyError:
            id = None
        return id

    def request_to_data(self, json_data: dict) -> list:
        """
        Creates a nested list containing products and all their informations.
        Will ignore incomplete products.

        json_data: json data from the OpenFoodFacts API
        """

        data = []
        for product in json_data["products"]:
            try:
                product_name = product["product_name"]
                nutriscore_grade = product["nutriscore_grade"]
                url = product["url"]
                stores = product["stores"]
                purchase_places = product["purchase_places"]
                pnns_groups_1 = product["pnns_groups_1"]
                pnns_groups_2 = \
                    self.match_category_with_id(product["pnns_groups_2"])
                if pnns_groups_2 is None:
                    continue
                data.append([product_name,
                            nutriscore_grade,
                            url,
                            stores,
                            purchase_places,
                            pnns_groups_1,
                            pnns_groups_2])

            except KeyError:
                # If the product doesn't have one of the keys, skip it.
                continue

        return data

    def insert_data_into_table(self, table: str, data: list) -> None:
        """
        Inserts data into a table.
        table: name of the table
        data: list of data to insert.

        data is a list of lists :
            data[0] is the list of attributes of the first product
            data[0][0] is the name of the first product
            data[0][1] is the nutriscore of the first product
            data[0][2] is the url of the first product
            data[0][3] is the list of stores of the first product
            data[0][4] is the list of purchase places of the first product
            data[0][5] is the pnns_groups_1 of the first product
            data[0][6] is the pnns_groups_2 of the first product
        """

        try:
            sql = mysql.connector.connect(host="localhost",
                                          user="root",
                                          password=ROOT_PASSWORD,
                                          database=DB_NAME)

            cursor = sql.cursor()
            if table == "product":
                print("Remplissage de la base de donnée avec OpenFoodFacts...")
                for row in data:
                    cursor.execute(
                        "INSERT INTO {} (\
                            product_name,\
                            nutriscore_grade,\
                            url,\
                            stores,\
                            purchase_places,\
                            pnns_groups_1,\
                            pnns_groups_2\
                        ) \
                        VALUES (%s, %s, %s, %s, %s, %s, %s)".format(table),
                        (row[0], row[1], row[2], row[3],
                         row[4], row[5], row[6]))

            elif table == "category":
                print("Attribution des clés étrangères...")
                for row in data:
                    cursor.execute(
                        "INSERT INTO {} (\
                            name\
                        ) \
                        VALUES (%s)".format(table),
                        (row,))

            sql.commit()
            print("Terminé !")

        except Error as e:
            print("Erreur de connexion à MySQL", e)

        except DatabaseError as e:
            print("Erreur lors de la création de la base de données", e)

        finally:
            if sql.is_connected():
                cursor.close()
                sql.close()


if __name__ == '__main__':
    db_setup = SetupDatabase()
