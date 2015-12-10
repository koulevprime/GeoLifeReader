#Input: Database with time-homogenized records.
#Output: ONE simulator ready files.
#Parameters: Number of users to output.
#            Weekday of interest.
#            Area of interest.
#            Time delta between records.
import logging
logging.basicConfig(
  level=logging.DEBUG,
  filename='/tmp/geolife.geostats.log',
  filemode='w'
)
logger = logging.getLogger("geolife")
stdout = logging.StreamHandler()
stdout.setLevel(logging.DEBUG)
logger.addHandler(stdout)

from schema import HomogenizedRecord
from config import getEngine
import argparse
from utils import timerange
from utils import ETACalculator
from utils import num_elements_in_time_range
from datetime import time
from datetime import timedelta
from sqlalchemy.orm import sessionmaker
import os
import numpy
import csv
from config import DECIMAL_DEGREES_TO_GRID_SCALE

Session = sessionmaker()
engine = getEngine()
Session.configure(bind=engine)


# Parse the command-line arguments.
def get_arguments():
  parser = argparse.ArgumentParser(
    description='Write out files for simulation.'
  )
  parser.add_argument(
    '-n', '--num-users',
    dest='num_users',
    help="Number of users to select from db",
    type=int,
    default=None,
  )

  parser.add_argument(
    '-d', '--time-delta',
    dest='time_delta',
    help="Number of seconds that should be between any two consecutive records",
    type=lambda x: timedelta(seconds=int(x)),
    default=timedelta(seconds=5),
  )
  parser.add_argument(
    '-o', '--output_directory',
    dest="output_directory",
    help='Directory to store created files (default: ./out)',
    default="./out",
    type=os.path.abspath,
  )

  args = parser.parse_args()
  return args


if __name__ == "__main__":
  session = Session()

  args = get_arguments()
  delta = args.time_delta
  output_directory = args.output_directory

  n = num_elements_in_time_range(start=time.min, end=time.max, step=delta)
  eta_til_completed = ETACalculator(n, "Geographic distribution over time")

  with open("distance_stats.csv", 'w') as output_file:
    fieldnames = ['time', 'centroid_lat', 'centroid_long', 'avg_distance', 'std_distance']
    writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    writer.writeheader()

    for t in timerange(time.min, time.max, delta):
      x_coords_of_records = []
      y_coords_of_records = []
      records = session.query(HomogenizedRecord).filter(
        HomogenizedRecord.time == t,
      )
      for r in records:
        x_coords_of_records.append(r.longitude)
        y_coords_of_records.append(r.latitude)

      centroid = numpy.array((
        numpy.mean(x_coords_of_records),
        numpy.mean(y_coords_of_records)
      ))

      distances = []
      for x, y in zip(x_coords_of_records, y_coords_of_records):
        p = numpy.array((x,y))
        d = numpy.linalg.norm(p-centroid)
        distances.append(d)

      avg_distance = numpy.mean(distances)
      std_distance = numpy.std(distances)
      print("Centroid: {0}".format(centroid))
      print("Average distance to centroid: {0}".format(avg_distance))
      print("Stddev distance: {0}".format(std_distance))

      writer.writerow({
        "time": t,
        "centroid_lat": centroid[1],
        "centroid_long": centroid[0],
        'avg_distance': avg_distance,
        'std_distance': std_distance,
      })

      # Calculate the average x and y coordinate
      eta_til_completed.checkpoint()
      logger.info(eta_til_completed.eta())

