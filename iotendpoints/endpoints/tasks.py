import requests
import json
from celery import shared_task
from celery.utils.log import get_task_logger
from influxdb.exceptions import InfluxDBClientError

from endpoints.utils import get_influxdb_client

logger = get_task_logger(__name__)


@shared_task
def save_to_influxdb(dbname, measurements):
    """
    Save valid `measurements` dictionary into InfluxDB database `dbname`.
    Log errors.
    :param dbname: Database name
    :param measurements: a valid InfluxDB dictionary.
    """
    iclient = get_influxdb_client(database=dbname)
    try:
        iclient.create_database(dbname)
        iclient.write_points(measurements)
        logger.info('Successfully saved InfluxDB object to database {}'.format(dbname))  # Goes to celery log
    except InfluxDBClientError as err:
        err_msg = '[InfluxDB] {}'.format(err)
        logger.error(err_msg)
        logger.error(json.dumps(measurements))


@shared_task
def push_ngsi_orion(data, url_root, username, password):
    # device_id = data['id']
    resp = None
    try:  # ...to update the entity...
        resp = requests.patch('{}/entities/{}/attrs/'.format(url_root, data['id']), auth=(username, password),
                              json={'NoiseLevelObserved': data['NoiseLevelObserved']})
    except Exception as err:
        logger.error('Something went wrong! Exception: {}'.format(e))
        print('Something went wrong PATCHing to Orion! Exception: {}'.format(err))

    # ...if updating failed, the entity probably doesn't exist yet so create it
    if not resp or (resp.status_code != 204):
        resp = requests.post('{}/entities/'.format(url_root), auth=(username, password), json=data)
    return resp
