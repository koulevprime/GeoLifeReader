#Input: Database with time-homogenized records.
#Output: ONE simulator ready files.
#Parameters: Number of users to output.
#            Weekday of interest.
#            Area of interest.
#            Time delta between records.
import logging
logging.basicConfig(
  level=logging.DEBUG,
  filename='/tmp/geolife.db2one.log',
  filemode='w'
)
logger = logging.getLogger("geolife")
stdout = logging.StreamHandler()
stdout.setLevel(logging.DEBUG)
logger.addHandler(stdout)

from schema import HomogenizedRecord
from raw.record import DayUser
from config import getEngine
from config import BOUNDS
from config import DECIMAL_DEGREES_TO_GRID_SCALE
from config import CONFIG_TEMPLATE
from config import CONFIG_FILE
import argparse
from utils import timerange
from utils import ETACalculator
from utils import num_elements_in_time_range
from datetime import time
from datetime import timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import and_
import os
from one import ExternalMovementReaderConverter
from utils import timeDifferenceSeconds
import pystache
import csv
import random

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

  parser.add_argument(
    '-i', '--interests-per-user',
    dest="interests",
    help='Number of social interests per user',
    type=int,
    default=25,
  )
  parser.add_argument(
    '-m', '--message-freq',
    dest="num_messages",
    help='How frequently messages should be generated (e.g. every 5 seconds)',
    type=int,
    default=10,
  )
  parser.add_argument(
    '-s', '--space-dimensions',
    dest="space",
    help='Total unique social interests (i.e. the social interest space)',
    type=int,
    default=200,
  )

  args = parser.parse_args()
  return args


def prepare_output(args):
  if not os.path.exists(args.output_directory):
    os.makedirs(args.output_directory)
    new_fileno = 0

  else:
    # Filenames start with 0.csv, and increase from there. Find the most recent
    #  filename.
    try:
      last_fileno = max([
        int(f.split(".")[0]) for f in os.listdir(args.output_directory) if f.endswith(".plt")
      ])
    except:
      new_fileno = 0
    else:
      new_fileno = last_fileno + 1

  logger.info("Creating new output file at {0}".format(
    "{0}.plt".format(new_fileno)
  ))
  return os.path.join(args.output_directory, "{0}.plt".format(new_fileno))


def write_to_file(records, f, converter):
  for r in records:
    f.write("{0}\n".format(converter(r)))


if __name__ == "__main__":
  session = Session()

  args = get_arguments()
  if args.num_users == 0:
    num_users = None
  else:
    num_users = args.num_users
  delta = args.time_delta
  output_directory = args.output_directory
  one_movement_filepath = prepare_output(args)

  logger.info("Exporting time-homogenized records from database")
  logger.info("Output directory: {0}".format(output_directory))
  logger.info("Time delta between records: {0}".format(delta))
  logger.info("Written movement file: {0}".format(one_movement_filepath))

  users = [u for u, in session.query(DayUser.id).filter(and_(
    DayUser.duration>7200,
    DayUser.count>500,
  )).all()]
  if num_users is not None and len(users) >= num_users:
    users = random.sample(users, num_users)

  else:
    num_users = len(users)

  logger.info("Number of users to be written out: {0}".format(num_users))
  n = num_elements_in_time_range(start=time.min, end=time.max, step=delta)
  eta_til_completed = ETACalculator(n, "DB to ONE output")
  converter = ExternalMovementReaderConverter(
    extent=BOUNDS,
    decimal_degree_scaling_factor=DECIMAL_DEGREES_TO_GRID_SCALE,
    users=users
  )

  with open(one_movement_filepath, "w") as f:
    logger.info("Writing converted and normalized records to {0}".format(
      one_movement_filepath
    ))
    f.write(
      "{minTime} {maxTime} "
      "{minX} {maxX} "
      "{minY} {maxY} "
      "{minZ} {maxZ}\n".format(
      **converter.getHeader()
    ))
    for t in timerange(time.min, time.max, delta):
      records = session.query(HomogenizedRecord).filter(
        HomogenizedRecord.time == t,
        HomogenizedRecord.user.in_(users),
      )
      write_to_file(records, f, converter)
      eta_til_completed.checkpoint()
      logger.info(eta_til_completed.eta())

  # Create message files and configuration files.
  leaf_directory = os.path.dirname(one_movement_filepath)

  # Convert centroid files to show ONE user addresses, not the original
  #  addresses.
  centroidFileUrl = os.path.join(leaf_directory, "centroids.csv")
  with open(centroidFileUrl, 'w') as finalizedCentroidFile:
    fieldnames = ['user', 'lat', 'long']
    writer = csv.DictWriter(finalizedCentroidFile, fieldnames=fieldnames)
    writer.writeheader()

    user_info = session.query(DayUser).filter(
      DayUser.id.in_(users)
    )
    for centroid_record in user_info:
      userID = centroid_record.id
      writer.writerow({
        "user": converter.user_to_addr_map[userID],
        "lat": centroid_record.centroid_lat,
        "long": centroid_record.centroid_lon,
      })

  # Create configuration file.
  duration = int(timeDifferenceSeconds(time.max, time.min))
  config_file = os.path.join(leaf_directory, CONFIG_FILE)
  logger.info("Writing out config file to {0}".format(config_file))
  with open(config_file, "w") as outfile:
    with open(CONFIG_TEMPLATE, 'r') as infile:
      outfile.write(pystache.render(
        infile.read(), {
        'centroidFile': centroidFileUrl,
        'num_hosts': num_users,
        'duration': duration,
        'max_x': converter.normalized_max_x,
        'max_y': converter.normalized_max_y,
        'external_movement_file': one_movement_filepath,
        'message_freq': args.num_messages,
        'social_interests': args.interests,
        'interest_space': args.space,
        'secondsToZero': 300,
        'max_host_addr': num_users-1,
        'leaf_directory': leaf_directory,
      }))
