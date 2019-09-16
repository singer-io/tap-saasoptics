from datetime import timedelta
import math
import singer
from singer import metrics, metadata, Transformer, utils
from singer.utils import strptime_to_utc, strftime
from tap_saasoptics.transform import transform_json
from tap_saasoptics.streams import STREAMS

LOGGER = singer.get_logger()


def write_schema(catalog, stream_name):
    stream = catalog.get_stream(stream_name)
    schema = stream.schema.to_dict()
    try:
        singer.write_schema(stream_name, schema, stream.key_properties)
    except OSError as err:
        LOGGER.info('OS Error writing schema for: {}'.format(stream_name))
        raise err


def write_record(stream_name, record, time_extracted):
    try:
        singer.messages.write_record(stream_name, record, time_extracted=time_extracted)
    except OSError as err:
        LOGGER.info('OS Error writing record for: {}'.format(stream_name))
        LOGGER.info('record: {}'.format(record))
        raise err


def get_bookmark(state, stream, default):
    if (state is None) or ('bookmarks' not in state):
        return default
    return (
        state
        .get('bookmarks', {})
        .get(stream, default)
    )


def write_bookmark(state, stream, value):
    if 'bookmarks' not in state:
        state['bookmarks'] = {}
    state['bookmarks'][stream] = value
    LOGGER.info('Write state for stream: {}, value: {}'.format(stream, value))
    singer.write_state(state)


def transform_datetime(this_dttm):
    with Transformer() as transformer:
        new_dttm = transformer._transform_datetime(this_dttm)
    return new_dttm


def process_records(catalog, #pylint: disable=too-many-branches
                    stream_name,
                    records,
                    time_extracted,
                    bookmark_field=None,
                    bookmark_type=None,
                    max_bookmark_value=None,
                    last_datetime=None,
                    last_integer=None):
    stream = catalog.get_stream(stream_name)
    schema = stream.schema.to_dict()
    stream_metadata = metadata.to_map(stream.metadata)

    with metrics.record_counter(stream_name) as counter:
        for record in records:
            # Transform record for Singer.io
            with Transformer() as transformer:
                transformed_record = transformer.transform(
                    record,
                    schema,
                    stream_metadata)

                # Reset max_bookmark_value to new value if higher
                if transformed_record.get(bookmark_field):
                    if max_bookmark_value is None or \
                        transformed_record[bookmark_field] > transform_datetime(max_bookmark_value):
                        max_bookmark_value = transformed_record[bookmark_field]

                if bookmark_field and (bookmark_field in transformed_record):
                    if bookmark_type == 'integer':
                        # Keep only records whose bookmark is after the last_integer
                        if transformed_record[bookmark_field] >= last_integer:
                            write_record(stream_name, transformed_record, \
                                time_extracted=time_extracted)
                            counter.increment()
                    elif bookmark_type == 'datetime':
                        last_dttm = transform_datetime(last_datetime)
                        bookmark_dttm = transform_datetime(transformed_record[bookmark_field])
                        # Keep only records whose bookmark is after the last_datetime
                        if bookmark_dttm >= last_dttm:
                            write_record(stream_name, transformed_record, \
                                time_extracted=time_extracted)
                            counter.increment()
                else:
                    write_record(stream_name, transformed_record, time_extracted=time_extracted)
                    counter.increment()

        return max_bookmark_value, counter.value


# Sync a specific endpoint
def sync_endpoint(client, #pylint: disable=too-many-branches
                  catalog,
                  state,
                  start_date,
                  stream_name,
                  path,
                  endpoint_config,
                  static_params,
                  bookmark_query_field_from=None,
                  bookmark_query_field_to=None,
                  bookmark_field=None,
                  bookmark_type=None,
                  data_key=None,
                  id_fields=None,
                  days_interval=None):


    # Get the latest bookmark for the stream and set the last_integer/datetime
    last_datetime = None
    last_integer = None
    max_bookmark_value = None
    if bookmark_type == 'integer':
        last_integer = get_bookmark(state, stream_name, 0)
        max_bookmark_value = last_integer
    else:
        last_datetime = get_bookmark(state, stream_name, start_date)
        max_bookmark_value = last_datetime

    write_schema(catalog, stream_name)

    # windowing: loop through date days_interval date windows from last_datetime to now_datetime
    now_datetime = utils.now()
    if bookmark_query_field_from and bookmark_query_field_to:
        # days_interval from config date_window_size, default = 60; passed to function from sync
        if not days_interval:
            days_interval = 60
        start_window = strptime_to_utc(last_datetime)
        end_window = start_window + timedelta(days=days_interval)
        if end_window > now_datetime:
            end_window = now_datetime
    else:
        start_window = strptime_to_utc(last_datetime)
        end_window = now_datetime
        diff_sec = (end_window - start_window).seconds
        days_interval = math.ceil(diff_sec / (3600 * 24)) # round-up difference to days
    endpoint_total = 0
    total_records = 0
    while start_window < now_datetime:
        LOGGER.info('START Sync for Stream: {}{}'.format(
            stream_name,
            ', Date window from: {} to {}'.format(start_window, end_window) \
                if bookmark_query_field_from else ''))
        params = static_params # adds in endpoint specific, sort, filter params
        if bookmark_query_field_from:
            # For datetime bookmark_type, tap allows from/to date window
            # For integer bookmark_type, tap allows from last_integer
            if bookmark_type == 'datetime':
                params[bookmark_query_field_from] = strftime(start_window)
            elif bookmark_type == 'integer':
                params[bookmark_query_field_from] = last_integer
            if bookmark_query_field_to:
                if bookmark_type == 'datetime':
                    params[bookmark_query_field_to] = strftime(end_window)

        # pagination: loop thru all pages of data using next (if not None)
        page = 1
        next_url = '{}/{}'.format(client.base_url, path)
        offset = 0
        limit = 100 # Default limit for SaaSOptics API, unable to change this in v1.0
        total_records = 0
        while next_url is not None:
            # Need URL querystring for 1st page; subsequent pages provided by next_url
            # querystring: Squash query params into string
            if page == 1 and not params == {}:
                querystring = '&'.join(['%s=%s' % (key, value) for (key, value) in params.items()])
            else:
                querystring = None
            LOGGER.info('URL for Stream {}: {}{}{}'.format(
                stream_name,
                next_url,
                '/' if page == 1 else '',
                '?{}'.format(querystring) if querystring else ''))

            # API request data
            data = {}
            data = client.get(
                url=next_url,
                path=path,
                params=querystring,
                endpoint=stream_name)

            # time_extracted: datetime when the data was extracted from the API
            time_extracted = utils.now()
            if not data or data is None or data == {}:
                total_records = 0
                break # No data results

            # Transform data with transform_json from transform.py
            # The data_key identifies the array/list of records below the <root> element
            # LOGGER.info('data = {}'.format(data)) # TESTING, comment out
            transformed_data = [] # initialize the record list
            # If a single record dictionary, append to a list[]
            if data_key is None:
                transformed_data = transform_json(data, stream_name, 'results')
            elif data_key in data:
                transformed_data = transform_json(data, stream_name, data_key)
            # LOGGER.info('transformed_data = {}'.format(transformed_data))  # TESTING, comment out
            if not transformed_data or transformed_data is None:
                LOGGER.info('No transformed data for data = {}'.format(data)) 
                total_records = 0
                break # No data results
            for record in transformed_data:
                for key in id_fields:
                    if not record.get(key):
                        LOGGER.info('xxx Missing key {} in record: {}'.format(key, record))

            # Process records and get the max_bookmark_value and record_count for the set of records
            max_bookmark_value, record_count = process_records(
                catalog=catalog,
                stream_name=stream_name,
                records=transformed_data,
                time_extracted=time_extracted,
                bookmark_field=bookmark_field,
                bookmark_type=bookmark_type,
                max_bookmark_value=max_bookmark_value,
                last_datetime=last_datetime,
                last_integer=last_integer)
            LOGGER.info('Stream {}, batch processed {} records'.format(
                stream_name, record_count))

            # set total_records and next_url for pagination
            total_records = data.get('count', 0)
            next_url = data.get('next', None)

            # Update the state with the max_bookmark_value for the stream
            if bookmark_field:
                write_bookmark(state, stream_name, max_bookmark_value)

            # to_rec: to record; ending record for the batch page
            to_rec = offset + limit
            if to_rec > total_records:
                to_rec = total_records

            LOGGER.info('Synced Stream: {}, page: {}, {} to {} of total records: {}'.format(
                stream_name,
                page,
                offset,
                to_rec,
                total_records))
            # Pagination: increment the offset by the limit (batch-size) and page
            offset = offset + limit
            page = page + 1

        # Increment date window
        start_window = end_window
        next_end_window = end_window + timedelta(days=days_interval)
        if next_end_window > now_datetime:
            end_window = now_datetime
        else:
            end_window = next_end_window
        endpoint_total = endpoint_total + total_records

    # Return endpoint_total across all batches
    return endpoint_total


# Currently syncing sets the stream currently being delivered in the state.
# If the integration is interrupted, this state property is used to identify
#  the starting point to continue from.
# Reference: https://github.com/singer-io/singer-python/blob/master/singer/bookmarks.py#L41-L46
def update_currently_syncing(state, stream_name):
    if (stream_name is None) and ('currently_syncing' in state):
        del state['currently_syncing']
    else:
        singer.set_currently_syncing(state, stream_name)
    singer.write_state(state)


def sync(client, config, catalog, state):
    if 'start_date' in config:
        start_date = config['start_date']

    # Get selected_streams from catalog, based on state last_stream
    #   last_stream = Previous currently synced stream, if the load was interrupted
    last_stream = singer.get_currently_syncing(state)
    LOGGER.info('last/currently syncing stream: {}'.format(last_stream))
    selected_streams = []
    for stream in catalog.get_selected_streams(state):
        selected_streams.append(stream.stream)
    LOGGER.info('selected_streams: {}'.format(selected_streams))

    if not selected_streams:
        return

    # Loop through selected_streams
    for stream_name in selected_streams:
        LOGGER.info('START Syncing: {}'.format(stream_name))
        update_currently_syncing(state, stream_name)
        endpoint_config = STREAMS[stream_name]
        path = endpoint_config.get('path', stream_name)
        bookmark_field = next(iter(endpoint_config.get('replication_keys', [])), None)
        total_records = sync_endpoint(
            client=client,
            catalog=catalog,
            state=state,
            start_date=start_date,
            stream_name=stream_name,
            path=path,
            endpoint_config=endpoint_config,
            static_params=endpoint_config.get('params', {}),
            bookmark_query_field_from=endpoint_config.get('bookmark_query_field_from'),
            bookmark_query_field_to=endpoint_config.get('bookmark_query_field_to'),
            bookmark_field=bookmark_field,
            bookmark_type=endpoint_config.get('bookmark_type'),
            data_key=endpoint_config.get('data_key', 'results'),
            id_fields=endpoint_config.get('key_properties'),
            days_interval=config.get('date_window_size', 60))

        update_currently_syncing(state, None)
        LOGGER.info('FINISHED Syncing: {}, total_records: {}'.format(
            stream_name,
            total_records))
