import csv
from datetime import datetime
import os

class FileReader:
    """
    A utility class to read and parse various types of CSV files.
    """

    @staticmethod
    def read_containers_info(file_name):
        """
        Read a CSV file and return a nested dictionary of container info.
        The CSV file should have headers in the first row.

        :param file_name: The relative or absolute path to the CSV file.
        :return: A dictionary {row_label: {column_label: value}}
        """
        matrix = {}
        file_path = os.path.abspath(file_name)

        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader)  # Read the header row

            for row in reader:
                row_label = row[0]
                row_dict = {headers[i]: int(row[i]) for i in range(1, len(row))}
                matrix[row_label] = row_dict

        return matrix

    @staticmethod
    def read_vessel_arrival_times(file_path):
        """
        Read a CSV file and return a dictionary mapping vessel names to arrival times.

        :param file_path: The relative or absolute path to the CSV file.
        :return: A dictionary {vessel_name: arrival_time (datetime)}
        """
        arrival_times = {}
        file_path = os.path.abspath(file_path)

        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)

            for row in reader:
                vessel_name = row[0]
                arrival_time = datetime.strptime(row[1], "%Y/%m/%d %H:%M:%S")
                arrival_times[vessel_name] = arrival_time

        return arrival_times

    @staticmethod
    def read_control_points_info(file_name):
        """
        Read a CSV file and return a dictionary mapping IDs to coordinates (x, y).

        :param file_name: The relative or absolute path to the CSV file.
        :return: A dictionary {id: (x, y)}
        """
        matrix = {}
        file_path = os.path.abspath(file_name)

        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)

            for index, row in enumerate(reader):
                if len(row) == 2:  # Ensure the row has exactly two parts
                    matrix[str(index)] = (float(row[0]), float(row[1]))

        return matrix
